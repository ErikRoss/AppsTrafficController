import logging
from abc import ABC
from hashlib import sha256
from typing import TYPE_CHECKING
from urllib import response

import requests
from flask import app, redirect, current_app

from database import db
from keitaro import KeitaroApi
from models import CampaignClick, Campaign, User, App, Transaction
from .exceptions import NoValidError, NotFoundError, SafeAbort
from .objects.event_app import EventApp


if TYPE_CHECKING:
    from controller import CampaignClickController


class ClickApp(ABC):

    def handle_app_click(self: "CampaignClickController"):
        self.log(self.LOG_WEB, "Detected inapp event")

        # App event
        app_event = self._get_app_event()
        self.log(self.LOG_APP, f"clid: {app_event.clid}, event: {app_event.event}")

        # Campaign click
        campaign_click = self._get_app_campaign_click(app_event)

        # Campaign
        campaign = self._get_app_campaign(campaign_click)

        try:

            # avoid duplicates
            self._avoid_event_duplicate(app_event, campaign_click)

            # compare user by event key and campaign owner
            self._validate_user_key(app_event, campaign)

            # set appclid (if not provided)
            if app_event.appclid and not campaign_click.appclid:
                campaign_click.appclid = app_event.appclid

            # set pay (if not provided)
            if app_event.pay:
                campaign_click.pay = app_event.pay

            # Send conversion to FB
            self.log(self.LOG_APP, f"Send conversion to FB: {app_event.event}")
            # optimization: send in the background
            self.global_threads_storage.run_in_thread(
                self.send_conversion_to_fb,
                app_event.event, campaign_click
            )
            campaign_click.update_conversion(app_event.event, conversion_sent=True)

            # Get User
            user = User.query.get(campaign.user_id)

            if not user:
                raise NotFoundError('User not found.')

            # no app in the campaign
            if not campaign_click.app_id or not (app := App.query.get(campaign_click.app_id)):
                self.log(
                    self.LOG_APP,
                    "App not found",
                    "error",
                    click=campaign_click,
                    campaign=campaign,
                    event="error",
                )
                raise SafeAbort

            logging.info(f"User balance: {user.balance}")

            # Handle event
            charge_amount = self._handle_event_and_get_charge_amount(campaign_click, campaign, app_event, app, user)

            # Save transaction
            new_transaction = Transaction(
                user_id=user.id,
                transaction_type="-",
                amount=float(charge_amount),
                reason=f"conversion {app_event.event.lower()}",
                geo=campaign_click.geo,
                app_id=campaign_click.app_id,
                os=campaign_click.device,
            )
            db.session.add(new_transaction)
            db.session.commit()
            logging.info(f"Charge amount: {charge_amount}")
            logging.info("Transaction added")
            logging.info(f"User balance: {user.balance}")
            self.log(self.LOG_APP, f"Conversion {app_event.event.lower()} sent. Charge amount: {charge_amount}")

        except SafeAbort:
            pass

        # final: redirect to offer url
        return redirect(self.make_offer_url(app_event, campaign, campaign_click))

    def _get_app_event(self: "CampaignClickController") -> EventApp:
        app_event = EventApp(self.request)

        if not app_event.clid:
            clid = self._get_app_event_clid(app_event)
            if clid:
                app_event.clid = clid
            else:
                raise NoValidError("No click id provided")

        return app_event
    
    def _get_app_event_clid(self: "CampaignClickController", app_event: EventApp) -> str:
        url = "https://userattribution.bleksi.com/search_user"
        
        args = {
            "user_agent": app_event.user_agent,
            "user_ip": app_event.ip
        }
        
        attributor_response = requests.post(url, json=args)
        if attributor_response.status_code == 200:
            user = attributor_response.json().get("user_data")
            if user:
                return user.get("panel_clid")
            else:
                raise NotFoundError("Click not found.")

    def _get_app_campaign_click(self: "CampaignClickController", app_event: EventApp) -> CampaignClick:
        campaign_click = CampaignClick.query.filter_by(click_id=app_event.clid).first()

        if not campaign_click:
            raise NotFoundError("Click not found.")

        return campaign_click

    def _get_app_campaign(self: "CampaignClickController", campaign_click: CampaignClick) -> Campaign:
        campaign = Campaign.query.get(campaign_click.campaign_id)

        if not campaign:
            raise NotFoundError("Campaign not found.")

        return campaign

    def _avoid_event_duplicate(self: "CampaignClickController", app_event: EventApp, campaign_click: CampaignClick) -> None:
        # no event
        if not app_event.event:
            self.log(self.LOG_APP, "No event provided", "error")
            raise SafeAbort

        # already installed
        if app_event.event.lower() == "install" and campaign_click.app_installed:
            self.log(self.LOG_APP, "App already installed")
            raise SafeAbort

        # already registered
        elif app_event.event.lower() == "reg" and campaign_click.app_registered:
            self.log(self.LOG_APP, "User already registered")
            raise SafeAbort

        # already deposited
        elif app_event.event.lower() == "dep" and campaign_click.app_deposited:
            self.log(self.LOG_APP, "User already deposited")
            raise SafeAbort

    def _validate_user_key(self: "CampaignClickController", app_event: EventApp, campaign: Campaign) -> None:
        # validate panel key (skip for `install` event)
        if app_event.event != "install":
            if not app_event.key:
                raise NoValidError("No key provided.")

            user_by_key = User.query.filter_by(panel_key=app_event.key).first()

            # handle error: no user by key
            if not user_by_key:
                raise NotFoundError("Key not found.")

            # handler error: unmatched user and campaign owner
            if user_by_key.id != campaign.user_id:
                raise NotFoundError("Key not valid.")

    @staticmethod
    def send_conversion_to_fb(event: str, campaign_click: CampaignClick) -> bool:
        logging.info(f"Send conversion to FB: {event}")
        
        if campaign_click.fbclid:
            key = sha256(campaign_click.fbclid.encode()).hexdigest()
        else:
            key = sha256(campaign_click.click_id.encode()).hexdigest()
        args = {
            "key": key,
            "event": event,
            "appclid": campaign_click.appclid
        }
        
        resp = requests.post(
            "https://eventservice.bleksi.com/send_conversion", json=args
        )
        if resp.status_code == 200:
            logging.info("Conversion sent")
            return True
        else:
            logging.info("Conversion not sent")
            return False

    def _handle_event_and_get_charge_amount(self: "CampaignClickController", campaign_click: CampaignClick, campaign: Campaign, app_event: EventApp, app: App, user: User) -> float:

        # Install event
        if app_event.event.lower() == "install":
            # optimization: send in the background
            self.global_threads_storage.run_in_thread(
                KeitaroApi().set_user_ununique,
                app.keitaro_id, self.request, str(app.id)
            )
            app.count_installs()
            campaign_click.install_app()
            charge_amount = current_app.config[
                "CONVERSION_INSTALL_PRICE_ANDROID"
                if app.operating_system.lower() == "android" else
                "CONVERSION_INSTALL_PRICE_IOS"
            ]
            user.subtract_balance(charge_amount)
            self.log(
                self.LOG_APP,
                f"App installed: {app.id} - {app.title}",
                "info",
                click=campaign_click,
                campaign=campaign,
                event="install",
            )

        # Registration event
        elif app_event.event.lower() == "reg":
            campaign_click.app_registered = True
            app.count_registrations()
            charge_amount = current_app.config[
                "CONVERSION_REGISTRATION_PRICE_ANDROID"
                if app.operating_system.lower() == "android" else
                "CONVERSION_REGISTRATION_PRICE_IOS"
            ]
            user.subtract_balance(charge_amount)
            self.log(
                self.LOG_APP,
                f"Registration sent: {app.id} - {app.title}",
                "info",
                click=campaign_click,
                campaign=campaign,
                event="registration",
            )

        # Deposit event
        elif app_event.event.lower() == "dep":
            campaign_click.app_deposited = True
            deposit_amount = self.request.args.get("amount", 0.0)
            campaign_click.deposit_amount = deposit_amount
            db.session.commit()
            app.count_deposits()
            charge_amount = current_app.config[
                "CONVERSION_DEPOSIT_PRICE_ANDROID"
                if app.operating_system.lower() == "android" else
                "CONVERSION_DEPOSIT_PRICE_IOS"
            ]
            user.subtract_balance(charge_amount)
            self.log(
                self.LOG_APP,
                f"Deposit [{deposit_amount}] sent: {app.id} - {app.title}",
                "info",
                click=campaign_click,
                campaign=campaign,
                event="deposit",
            )

        # unrecognized event
        else:
            logging.info("Charge amount: 0.00")
            logging.info(f"User balance: {user.balance}")
            raise SafeAbort

        return charge_amount

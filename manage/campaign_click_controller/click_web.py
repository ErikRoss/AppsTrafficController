import logging
import traceback
from abc import ABC
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import TYPE_CHECKING, Type

import requests
from flask import redirect, g

from apps_balancer import AppsBalancer
from config import SERVICE_NAME, SERVICE_TAG, TIME_ZONE
from keitaro import KeitaroApi
from manage.render_page import emergency, render_page
from models import CampaignClick, Campaign, App, Landing
from .exceptions import SafeAbort, SafeAbortAndResponse, BaseError
from .objects.event_web import EventWeb


if TYPE_CHECKING:
    from controller import CampaignClickController


class ClickWeb(ABC):

    def handle_web_click(self: "CampaignClickController"):
        priority_executor = ThreadPoolExecutor(max_workers=1)

        try:

            # Web event
            web_event = self._get_web_event()
            self.log(self.LOG_WEB, f"Requested campaign id: {web_event.uchsik}. Request args: {self.request.args}")

            # Campaign
            campaign = self._get_web_campaign(web_event)
            self.log(self.LOG_WEB, f"Campaign found: {campaign.title}. Generating click id")

            logging.info("Generate click id")
            logging.info("Request args:\n" + str(self.request.args))

            # optimization: start getting the app here
            selected_app_future = priority_executor.submit(
                self.global_threads_storage.wrap_in_context, AppsBalancer(
                    campaign, 
                    self.request, 
                    web_event.psa, 
                    web_event.psa_type
                    ).select_relevant_app
            )

            # Campaign click
            campaign_click = self._get_web_campaign_click(web_event, campaign)

            # TODO check double click
            click_double = False

            # is new click: save
            if not click_double:
                # optimization: execute in the global background
                self.global_threads_storage.run_in_thread(self.save_click, web_event)

            # If the OS does not match
            #  try to redirect to a reserve app for the actual OS
            if campaign.operating_system.lower() != campaign_click.device:
                self.log(self.LOG_WEB, "OS mismatch. Redirect to reserve app")
                # Find reserve app for the current os
                reserve_app = AppsBalancer(request=self.request).select_reserve_app(campaign_click.device)
                raise self._app_redirect(reserve_app, "Reserve", web_event, campaign_click, campaign)

            logging.info("Select app")
            selected_app = selected_app_future.result()

            # Update metrics
            if selected_app:
                logging.info(f"Selected app id: {selected_app.id}")

                # initialize campaign OS from App
                if not campaign.operating_system:
                    campaign.operating_system = selected_app.operating_system

                # initialize apps_stats for the campaign
                if not campaign.apps_stats:
                    campaign.apps_stats = [{"id": app.id, "weight": 100 // len(campaign.apps), "visits": 0} for app in campaign.apps]

                # find the item by app.id and increase visits +1
                campaign.apps_stats = list(map(lambda app: {**app, "visits": app["visits"] + 1} if int(app["id"]) == int(selected_app.id) else app, campaign.apps_stats))

                # initialize campaign click app
                if not campaign_click.app_id:
                    campaign_click.app_id = selected_app.id

            # try to Redirect to the app
            raise self._app_redirect(selected_app, "Selected", web_event, campaign_click, campaign)

        except (BaseError, SafeAbort):
            pass

        except SafeAbortAndResponse as exc:
            return exc.response

        except:
            logging.error(traceback.format_exc())
            self.log(self.LOG_WEB, f"{traceback.format_exc()}", "error")

        finally:
            priority_executor.shutdown(wait=False)

        return emergency()

    def _get_web_event(self: "CampaignClickController") -> EventWeb:
        web_event = EventWeb(self.request)

        if not web_event.uchsik:
            self.log(self.LOG_WEB, "uchsik is empty", "error")
            raise SafeAbort

        return web_event

    def _get_web_campaign(self: "CampaignClickController", web_event: EventWeb) -> Campaign:
        campaign = g.session.query(Campaign).filter_by(hash_code=web_event.uchsik).first()

        if not campaign:
            self.log(self.LOG_WEB, "Campaign not found", "error")
            raise SafeAbort

        return campaign

    def _get_web_campaign_click(self: "CampaignClickController", web_event: EventWeb, campaign: Campaign) -> CampaignClick:
        # prepare parameters
        request_parameters = {
            key: value for key, value in self.request.args.items()
            if key not in ['uchsik']
        }

        # Send request to Keitaro Api
        #  check and get user data
        user_data = KeitaroApi().check_is_user_bot(
            self.request,
            request_parameters,
            web_event.rma,
            web_event.clid,
            web_event.fbclid,
            web_event.domain,
            web_event.ulb
        )

        # Prepare Campaign click
        campaign_click = CampaignClick(
            click_id=web_event.clid,
            domain=web_event.domain,
            fbclid=web_event.fbclid,
            rma=web_event.rma,
            ulb=web_event.ulb,
            kclid=user_data["kclid"],
            pay=web_event.pay,
            request_parameters=request_parameters,
            campaign_hash=web_event.uchsik,
            campaign_id=campaign.id,
            campaign=campaign,
            offer_url=campaign.offer_url,
            ip=user_data["ip"],
            user_agent=user_data["user_agent"],
            referer=self.request.headers.get("Referer") or "Unknown",
            timestamp=datetime.now(TIME_ZONE),
            blocked=user_data["result"] == "block",
            geo=user_data["geo"].lower() if user_data["geo"] else None,
            device=user_data["device"].lower() if user_data["device"] else None,
            hash_id=None,
        )
        g.session.add(campaign_click)
        logging.info(f"Blocked by Keitaro: {campaign_click.blocked}")

        if campaign.status != "active":
            campaign_click.result = "inactive campaign"
            self.log(self.LOG_WEB, "Inactive campaign. Redirect to emergency landing")
            raise SafeAbort

        # click blocked, redirect...
        if campaign_click.blocked:
            self.log(self.LOG_WEB, "Bot detected. Redirect to landing")

            # no campaign landing
            if not campaign.landing_id or not (landing := g.session.query(Landing).get(campaign.landing_id)):
                campaign_click.result = "landing not found"
                self.log(self.LOG_WEB, "Landing not found. Redirect to emergency landing")
                raise SafeAbort

            # landing is not active
            if landing.status != "active":
                campaign_click.result = "inactive landing"
                self.log(self.LOG_WEB, "Inactive landing. Redirect to emergency landing")
                raise SafeAbort

            # render landing
            campaign_click.result = "show landing"
            self.log(self.LOG_WEB, "Landing found. Rendering landing")
            raise SafeAbortAndResponse(render_page(landing))

        return campaign_click

    def _app_redirect(self: "CampaignClickController", app: App, log_tag: str, web_event: EventWeb, campaign_click: CampaignClick, campaign: Campaign) -> SafeAbortAndResponse | Type[SafeAbort]:
        self.log(self.LOG_WEB, "Saving User")
        self.global_threads_storage.run_in_thread(self.save_user, web_event)

        # Redirect to app
        if app and app.status == "active":
            campaign_click.result = "redirected to %s app" % log_tag.lower()
            campaign_click.app_id = campaign_click.app_id or app.id

            redirect_url = app.url.replace("PANELCLID", campaign_click.click_id)
            app.count_views()

            self.log(
                self.LOG_WEB,
                "%s app found: %s - %s" % (log_tag, app.id, app.title),
                "info",
                click=campaign_click,
                campaign=campaign,
                event="click",
            )

            return SafeAbortAndResponse(redirect(redirect_url))

        # no app
        campaign_click.result = "not found app"
        self.log(self.LOG_WEB, "%s app not found. Generating url for redirect" % log_tag)

        # or Redirect to offer
        if campaign.offer_url:
            offer_url = self.make_offer_url(web_event, campaign, campaign_click)
            self.log(self.LOG_WEB, f"Redirect to offer url: {offer_url}")
            return SafeAbortAndResponse(redirect(offer_url))

        # or Render emergency page
        self.log(self.LOG_WEB, "Offer url not found. Redirect to emergency landing", "error")
        return SafeAbort

    @staticmethod
    def save_click(web_event: EventWeb) -> requests.Response:        
        base_url = "https://eventservice.bleksi.com/save_click"

        args = {
            "click_id": web_event.clid,
            "domain": web_event.domain,
            "rma": web_event.rma,
            "ulb": web_event.ulb,
            "xcn": web_event.pay,
            "fbclid": web_event.fbclid,
            "gclid": web_event.gclid,
            "ttclid": web_event.ttclid,
            "initiator": SERVICE_NAME,
        }
        
        return requests.post(base_url, json=args)

    @staticmethod
    def save_user(web_event: EventWeb) -> requests.Response:
        base_url = "https://userattribution.bleksi.com/save_user"

        args = {
            "user_agent": web_event.user_agent,
            "user_ip": web_event.ip,
            "panel_clid": web_event.clid,
            "initiator": SERVICE_NAME,
            "service_tag": SERVICE_TAG,
        }
        
        attributor_response = requests.post(base_url, json=args)

        return attributor_response

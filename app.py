from calendar import c
from datetime import datetime
from hashlib import sha256
import logging
import os
from logging import Formatter, FileHandler
from random import randint
import traceback
import pytz

import requests
import secrets
from urllib.parse import urlencode

from flask import (
    Flask,
    abort,
    current_app,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
)

from flask_cors import CORS

# from flask_caching import Cache
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import generate_password_hash

from apps_balancer import AppsBalancer
from config import SQLALCHEMY_DATABASE_URI as DB_URI
from database import db
from keitaro import KeitaroApi
from logger import save_log_message
from models import App, Campaign, Landing, CampaignClick, Transaction, User


# ----------------------------------------------------------------------------#
# App Config.
# ----------------------------------------------------------------------------#

app = Flask(__name__)
app.config.from_object("config")
app.app_context().push()
CORS(app)

db.init_app(app)
migrate = Migrate(app, db)
from client_api import api_endpoint, create_test_admin, create_registrant

engine = create_engine(DB_URI)
Session = scoped_session(sessionmaker(bind=engine))

jwt_manager = JWTManager(app)

app.register_blueprint(api_endpoint, url_prefix="/api")


timezone = pytz.timezone("Europe/Kiev")

# Automatically tear down SQLAlchemy.
@app.before_request
def before_request():
    g.session = Session()


@app.teardown_request
def shutdown_session(exception=None):
    if hasattr(g, "session"):
        g.session.commit()
        g.session.close()


@jwt_manager.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    user_id = jwt_data["sub"]
    user = db.session.get(User, user_id)
    return user


# Controllers


# @app.route("/", methods=["GET"], host="yoursapps3.online")
def handle_inapp():
    """
    Handle inapp events
    """
    clid = request.args.get("clid")
    appclid = request.args.get("appclid")
    pay = request.args.get("pay")
    if clid:
        if request.host == "flow.symbioticapps.com":
            event = "install"
        else:
            event = request.args.get("event")
        save_log_message(
            "Inapp receiver",
            f"clid: {clid}, event: {event}",
        )

        campaign_click = CampaignClick.query.filter_by(click_id=clid).first()
        if campaign_click:
            campaign_obj = Campaign.query.get(campaign_click.campaign_id)
            if not campaign_obj:
                save_log_message("Inapp receiver", "Campaign not found", "error")
                return (
                    jsonify({"error": "Campaign not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )

            clid = {"clid": clid}
            kclid = {"kclid": campaign_click.kclid}
            if "?" in campaign_click.offer_url:
                url = "&".join(
                    [
                        campaign_click.offer_url,
                        urlencode(clid),
                        urlencode(kclid),
                        urlencode(campaign_click.request_parameters),
                        urlencode(campaign_obj.custom_parameters),
                    ]
                )
            else:
                url = (
                    campaign_click.offer_url
                    + "?"
                    + "&".join(
                        [
                            urlencode(clid),
                            urlencode(kclid),
                            urlencode(campaign_click.request_parameters),
                            urlencode(campaign_obj.custom_parameters),
                        ]
                    )
                )
            
            if event:
                if event.lower() == "install" and campaign_click.app_installed:
                    save_log_message(
                        "Inapp receiver",
                        "App already installed",
                    )
                    return redirect(url)
                elif event.lower() == "reg" and campaign_click.app_registered:
                    save_log_message(
                        "Inapp receiver",
                        "User already registered",
                    )
                    return redirect(url)
                elif event.lower() == "dep" and campaign_click.app_deposited:
                    save_log_message(
                        "Inapp receiver",
                        "User already deposited",
                    )
                    return redirect(url)
                
                

            if event != "install":
                key = request.args.get("key")
                if not key:
                    save_log_message("Inapp receiver", "No key provided", "error")
                    return (
                        jsonify({"error": "No key provided."}),
                        400,
                        {"Content-Type": "application/json"},
                    )

                user = User.query.filter_by(panel_key=key).first()
                if not user:
                    save_log_message("Inapp receiver", "Key not found", "error")
                    return (
                        jsonify({"error": "Key not found."}),
                        404,
                        {"Content-Type": "application/json"},
                    )

                if user.id != campaign_obj.user_id:
                    save_log_message("Inapp receiver", "Key not valid", "error")
                    return (
                        jsonify({"error": "Key not valid."}),
                        404,
                        {"Content-Type": "application/json"},
                    )

            if event:
                save_log_message(
                    "Inapp receiver",
                    f"Send conversion to FB: {event}",
                )
                if appclid and not campaign_click.appclid:
                    campaign_click.appclid = appclid
                
                if pay:
                    campaign_click.pay = pay
                
                conversion_sent = send_conversion_to_fb(event, campaign_click)
                campaign_click.update_conversion(event, conversion_sent)

                user = User.query.get(campaign_obj.user_id)
                if user:
                    if not campaign_click.app_id:
                        save_log_message(
                            "Inapp receiver",
                            "App not found",
                            "error",
                            click=campaign_click,
                            campaign=campaign_obj,
                            event="error",
                        )
                        logging.info(f"App not found in click {campaign_click.id}")
                        return redirect(url)

                    logging.info(f"User balance: {user.balance}")
                    app_obj = App.query.get(campaign_click.app_id)
                    if (
                        app_obj
                        and event.lower() == "install"
                        and not campaign_click.app_installed
                    ):
                        KeitaroApi().set_user_ununique(
                            app_obj.keitaro_id, request, str(app_obj.id)
                        )
                        app_obj.count_installs()
                        campaign_click.install_app()
                        if app_obj.operating_system.lower() == "android":
                            charge_amount = current_app.config[
                                "CONVERSION_INSTALL_PRICE_ANDROID"
                            ]
                        else:
                            charge_amount = current_app.config[
                                "CONVERSION_INSTALL_PRICE_IOS"
                            ]
                        user.subtract_balance(charge_amount)
                        save_log_message(
                            "Inapp receiver",
                            f"App installed: {app_obj.id} - {app_obj.title}",
                            "info",
                            click=campaign_click,
                            campaign=campaign_obj,
                            event="install",
                        )
                    elif app_obj and event.lower() == "reg":
                        campaign_click.app_registered = True
                        app_obj.count_registrations()
                        if app_obj.operating_system == "android":
                            charge_amount = current_app.config[
                                "CONVERSION_REGISTRATION_PRICE_ANDROID"
                            ]
                        else:
                            charge_amount = current_app.config[
                                "CONVERSION_REGISTRATION_PRICE_IOS"
                            ]
                        user.subtract_balance(charge_amount)
                        save_log_message(
                            "Inapp receiver",
                            f"Registration sent: {app_obj.id} - {app_obj.title}",
                            "info",
                            click=campaign_click,
                            campaign=campaign_obj,
                            event="registration",
                        )
                    elif app_obj and event.lower() == "dep":
                        campaign_click.app_deposited = True
                        deposit_amount = request.args.get("amount", 0.0)
                        campaign_click.deposit_amount = deposit_amount
                        db.session.commit()

                        app_obj.count_deposits()
                        if app_obj.operating_system == "android":
                            charge_amount = current_app.config[
                                "CONVERSION_DEPOSIT_PRICE_ANDROID"
                            ]
                        else:
                            charge_amount = current_app.config[
                                "CONVERSION_DEPOSIT_PRICE_IOS"
                            ]
                        user.subtract_balance(charge_amount)
                        save_log_message(
                            "Inapp receiver",
                            f"Deposit [{deposit_amount}] sent: {app_obj.id} - {app_obj.title}",
                            "info",
                            click=campaign_click,
                            campaign=campaign_obj,
                            event="deposit",
                        )
                    else:
                        logging.info("Charge amount: 0.00")
                        logging.info(f"User balance: {user.balance}")
                        if event.lower() == "install" and campaign_click.app_installed:
                            save_log_message(
                                "Inapp receiver",
                                "App already installed",
                            )
                        return redirect(url)

                    new_transaction = Transaction(
                        user_id=user.id,
                        transaction_type="-",
                        amount=float(charge_amount),
                        reason=f"conversion {event.lower()}",
                        geo=campaign_click.geo,
                        app_id=campaign_click.app_id,
                        os=campaign_click.device,
                    )
                    db.session.add(new_transaction)
                    db.session.commit()
                    logging.info(f"Charge amount: {charge_amount}")
                    logging.info("Transaction added")
                    logging.info(f"User balance: {user.balance}")
                    save_log_message(
                        "Inapp receiver",
                        f"Conversion {event.lower()} sent. Charge amount: {charge_amount}",
                    )
                    return redirect(url)
            else:
                save_log_message("Inapp receiver", "No event provided", "error")
                return redirect(url)
        else:
            save_log_message("Inapp receiver", "Click not found", "error")
            return (
                jsonify({"error": "Click not found."}),
                404,
                {"Content-Type": "application/json"},
            )
    else:
        save_log_message("Inapp receiver", "No click id provided", "error")
        return (
            jsonify({"error": "No click id provided."}),
            400,
            {"Content-Type": "application/json"},
        )


@app.route("/<path:filename>", methods=["GET"])
def get_resources(filename):
    if "." in filename:
        cookie_key = request.cookies.get("ti3948gh3d")
        logging.info(f"Cookie key: {cookie_key}")
        if cookie_key:
            landing_id = get_number_from_secret_key(str(cookie_key))
            landing = Landing.query.get(landing_id)
            if landing:
                return send_from_directory(
                    f"templates/{landing.working_directory}",
                    filename,
                    as_attachment="html" not in filename,
                )

            return send_from_directory(
                "static",
                filename,
                as_attachment="html" not in filename,
            )
        else:
            logging.info("No cookie found")
            logging.info(filename)
            return send_from_directory(
                "static",
                filename,
                as_attachment="html" not in filename,
            )
    else:
        return home()


@app.route("/", methods=["GET"])
def home():
    if not request:
        return (
            jsonify({"error": "No request found."}),
            400,
            {"Content-Type": "application/json"},
        )

    save_log_message(
        "Receiver",
        f"Requested url: {request.url} from {request.headers.get('X-Forwarded-For', request.remote_addr)}",
    )
    logging.info(f"Request: {request}")
    
    if request.host in ["flow.symbioticapps.com", "events.symbioticapps.com"]:
        save_log_message(
            "Receiver",
            "Detected inapp event",
        )
        return handle_inapp()
    
    try:
        campaign_id = request.args.get("uchsik")
        save_log_message(
            "Receiver",
            f"Requested campaign id: {campaign_id}. Request args: {request.args}",
        )
        logging.info(f"Campaign id: {campaign_id}")
        if campaign_id:
            campaign = g.session.query(Campaign).filter_by(hash_code=campaign_id).first()
            if not campaign:
                save_log_message("Receiver", "Campaign not found", "error")
                return emergency()
        else:
            return emergency()

        save_log_message(
            "Receiver",
            f"Campaign found: {campaign.title}. Generating click id",
        )
        
        # user_agent = request.headers.get("User-Agent")
        # if not user_agent:
        #     user_agent = "Unknown"
        # logging.info(f"User agent: {user_agent}")
        # user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        # if not user_ip:
        #     user_ip = "Unknown"
        # logging.info(f"User ip: {user_ip}")
        
        # fbclid = request.args.get("fbclid", "Unknown")
        # gclid = request.args.get("gclid", "Unknown")
        # hash_id = sha256((fbclid + gclid).encode()).hexdigest()[:6]
        # # hash_id = sha256((user_agent + user_ip).encode()).hexdigest()[:6]
        
        # campaign_click = CampaignClick.query.filter_by(hash_id=hash_id).order_by(CampaignClick.id.desc()).limit(100).first()
        click_double = False
        # logging.info(f"Click double: {click_double}")
        # if not campaign_click:
        logging.info("Generate click id")
        logging.info("Request args:\n" + str(request.args))
        click_id = generate_click_id()
        fbclid = request.args.get("fbclid", "Unknown")
        rma = request.args.get("rma", "Unknown")
        xcn = int(request.args.get("pay", randint(120, 210)))
        request_parameters = {}
        for key, value in request.args.items():
            if key not in ["uchsik"]:
                request_parameters[key] = value
        domain = request.headers.get("Host")
        ulb = randint(10000000, 99999999)
        
        # keitaro_start = datetime.now()
        user_data = KeitaroApi().check_is_user_bot(
            request,
            request_parameters,
            rma,
            click_id,
            fbclid,
            domain,
            ulb
            )
        # keitaro_time = datetime.now() - keitaro_start

        campaign_click = CampaignClick(
            click_id=click_id,
            domain=domain,
            fbclid=fbclid or "Unknown",
            rma=rma or "Unknown",
            ulb=ulb,
            kclid=user_data["kclid"],
            pay=xcn,
            request_parameters=request_parameters,
            campaign_hash=campaign_id,
            campaign_id=campaign.id,
            campaign=campaign,
            offer_url=campaign.offer_url,
            ip=user_data["ip"],
            user_agent=user_data["user_agent"],
            referer=request.headers.get("Referer") or "Unknown",
            timestamp=datetime.now(timezone),
            blocked=user_data["result"] == "block",
            geo=user_data["geo"].lower() if user_data["geo"] else None,
            device=user_data["device"].lower() if user_data["device"] else None,
            hash_id=None,
        )
        g.session.add(campaign_click)
            
        clid = {"clid": campaign_click.click_id}
        kclid = {"kclid": campaign_click.kclid}
        logging.info(f"Blocked by Keitaro: {campaign_click.blocked}")

        if campaign.status != "active":
            campaign_click.result = "inactive campaign"
            save_log_message(
                "Receiver",
                "Inactive campaign. Redirect to emergency landing",
            )

            return emergency()

        if campaign_click.blocked:
            save_log_message(
                "Receiver",
                "Bot detected. Redirect to landing",
            )
            if campaign.landing_id:
                landing = g.session.query(Landing).get(campaign.landing_id)
            else:
                campaign_click.result = "landing not found"
                save_log_message(
                    "Receiver",
                    "Landing not found. Redirect to emergency landing",
                )

                return emergency()

            if landing and landing.status == "active":
                campaign_click.result = "show landing"
                save_log_message(
                    "Receiver",
                    "Landing found. Rendering landing",
                )

                return render_page(landing)
            elif landing and landing.status != "active":
                campaign_click.result = "inactive landing"
                save_log_message(
                    "Receiver",
                    "Inactive landing. Redirect to emergency landing",
                )

                return emergency()
            else:
                campaign_click.result = "landing not found"
                save_log_message(
                    "Receiver",
                    "Landing not found. Redirect to emergency landing",
                )

                return emergency()
        elif not campaign_click.blocked:
            if not click_double:
                fbclid_hash = sha256(campaign_click.fbclid.encode()).hexdigest()
                save_click(click_id, rma, fbclid, fbclid_hash, domain, ulb, xcn)
            
            if campaign.operating_system.lower() != campaign_click.device:
                save_log_message(
                    "Receiver",
                    "OS mismatch. Redirect to reserve app",
                )
                logging.info("OS mismatch")
                balancer_start = datetime.now()
                reserve_app = AppsBalancer(request=request).select_reserve_app(
                    campaign_click.device
                )
                logging.info(f"Balancer time: {(datetime.now() - balancer_start).total_seconds()}")
                
                if reserve_app:
                    campaign_click.result = "redirected to reserve app by OS"

                    if reserve_app and reserve_app.status == "active":
                        if not campaign_click.app_id:
                            campaign_click.app_id = reserve_app.id

                        redirect_url = reserve_app.url.replace(
                            "PANELCLID", 
                            campaign_click.click_id
                            )
                        reserve_app.count_views()
                        save_log_message(
                            "Receiver",
                            f"Reserve app found: {reserve_app.id} - {reserve_app.title}",
                            "info",
                            click=campaign_click,
                            campaign=campaign,
                            event="click",
                        )
                        logging.info(
                            f"Reserve app found: {reserve_app.id} - {reserve_app.title}"
                        )

                        return redirect(redirect_url)
                    else:
                        campaign_click.result = "not found app"
                        save_log_message(
                            "Receiver",
                            "Reserve app not found. Generating url for redirect",
                        )
                        if campaign.offer_url:
                            if "?" in campaign_click.offer_url:
                                redirect_url = "&".join(
                                    [
                                        campaign_click.offer_url,
                                        urlencode(clid),
                                        urlencode(kclid),
                                        urlencode(campaign_click.request_parameters),
                                        urlencode(campaign.custom_parameters),
                                    ]
                                )
                            else:
                                redirect_url = (
                                    campaign_click.offer_url
                                    + "?"
                                    + "&".join(
                                        [
                                            urlencode(clid),
                                            urlencode(kclid),
                                            urlencode(
                                                campaign_click.request_parameters
                                            ),
                                            urlencode(campaign.custom_parameters),
                                        ]
                                    )
                                )
                            save_log_message(
                                "Receiver",
                                f"Redirect to offer url: {redirect_url}",
                            )
                            return redirect(redirect_url)
                        else:
                            save_log_message(
                                "Receiver",
                                "Offer url not found. Redirect to emergency landing",
                                "error",
                            )
                            return emergency()

                if campaign.offer_url:
                    if "?" in campaign_click.offer_url:
                        redirect_url = "&".join(
                            [
                                campaign_click.offer_url,
                                urlencode(clid),
                                urlencode(kclid),
                                urlencode(campaign_click.request_parameters),
                                urlencode(campaign.custom_parameters),
                            ]
                        )
                    else:
                        redirect_url = (
                            campaign_click.offer_url
                            + "?"
                            + "&".join(
                                [
                                    urlencode(clid),
                                    urlencode(kclid),
                                    urlencode(campaign_click.request_parameters),
                                    urlencode(campaign.custom_parameters),
                                ]
                            )
                        )
                    save_log_message(
                        "Receiver",
                        f"Redirect to offer url: {redirect_url}",
                    )
                    return redirect(redirect_url)
                else:
                    save_log_message(
                        "Receiver",
                        "Offer url not found. Redirect to emergency landing",
                        "error",
                    )
                    return emergency()

            apps_stats = campaign.apps_stats
            if not apps_stats:
                apps_stats = generate_apps_stats(campaign.apps)

            logging.info("Select app")
            balancer_start = datetime.now()
            selected_app = AppsBalancer(campaign, request).select_relevant_app()
            logging.info(f"Balancer time: {(datetime.now() - balancer_start).total_seconds()}")

            if not selected_app:
                campaign_click.result = "not found app"
                if campaign.offer_url:
                    if "?" in campaign_click.offer_url:
                        redirect_url = "&".join(
                            [
                                campaign_click.offer_url,
                                urlencode(clid),
                                urlencode(kclid),
                                urlencode(campaign_click.request_parameters),
                                urlencode(campaign.custom_parameters),
                            ]
                        )
                    else:
                        redirect_url = (
                            campaign_click.offer_url
                            + "?"
                            + "&".join(
                                [
                                    urlencode(clid),
                                    urlencode(kclid),
                                    urlencode(campaign_click.request_parameters),
                                    urlencode(campaign.custom_parameters),
                                ]
                            )
                        )
                    save_log_message(
                        "Receiver",
                        f"Redirect to offer url: {redirect_url}",
                    )
                    return redirect(redirect_url)
                else:
                    save_log_message(
                        "Receiver",
                        "Offer url not found. Redirect to emergency landing",
                        "error",
                    )
                    return emergency()

            if selected_app:
                logging.info(f"Selected app id: {selected_app.id}")
                if not campaign.operating_system:
                    campaign.operating_system = selected_app.operating_system  # type: ignore
                campaign.apps_stats = update_apps_stats(apps_stats, selected_app.id)
            if not campaign_click.app_id:
                campaign_click.app_id = selected_app.id
            # campaign_click.app = selected_app
            
            if selected_app and selected_app.status == "active":
                campaign_click.result = "redirected to app"
                redirect_url = selected_app.url.replace(
                    "PANELCLID", 
                    campaign_click.click_id
                    )
                selected_app.count_views()
                save_log_message(
                    "Receiver",
                    f"App found: {selected_app.id} - {selected_app.title}",
                )
                logging.info(f"App found: {selected_app.id} - {selected_app.title}. Redirect to {redirect_url}")

                return redirect(redirect_url)
                # return (
                #     jsonify(
                #         {
                #             "keitaro_time": f"{keitaro_time.total_seconds()} sec",
                #             "app_id": app_obj.id,
                #             "app_title": app_obj.title,
                #             "app_url": redirect_url,
                #         }
                #     ),
                #     200,
                #     {"Content-Type": "application/json"},
                # )
            else:
                campaign_click.result = "not found app"
                save_log_message(
                    "Receiver",
                    "App not found. Generating url for redirect",
                )
                if campaign.offer_url:
                    if "?" in campaign_click.offer_url:
                        redirect_url = "&".join(
                            [
                                campaign_click.offer_url,
                                urlencode(clid),
                                urlencode(kclid),
                                urlencode(campaign_click.request_parameters),
                                urlencode(campaign.custom_parameters),
                            ]
                        )
                    else:
                        redirect_url = (
                            campaign_click.offer_url
                            + "?"
                            + "&".join(
                                [
                                    urlencode(clid),
                                    urlencode(kclid),
                                    urlencode(campaign_click.request_parameters),
                                    urlencode(campaign.custom_parameters),
                                ]
                            )
                        )
                    save_log_message(
                        "Receiver",
                        f"Redirect to offer url: {redirect_url}",
                    )
                    logging.info(f"App not found. Redirect to {redirect_url}")
                    return redirect(redirect_url)
                else:
                    save_log_message(
                        "Receiver",
                        "Offer url not found. Redirect to emergency landing",
                        "error",
                    )
                    logging.info("App not found. Redirect to emergency landing")
                    return emergency()
        else:
            campaign_click.result = "tracking error"
            save_log_message(
                "Receiver", "Tracking error. Redirect to emergency landing", "error"
            )
            logging.error("Tracking error")
            return emergency()
    except Exception:
        logging.error(traceback.format_exc())
        save_log_message("Receiver", f"{traceback.format_exc()}", "error")
        return emergency()


@app.route("/emergency", methods=["GET", "POST"])
def emergency():
    return render_template("pages/emergency_page.html")


# Redirections


def gererate_secret_key_from_number(number):
    key_length = 60
    random_string = secrets.token_hex(key_length // 2)

    return random_string + str(number)


def get_number_from_secret_key(key):
    return key[60:]


def render_page(landing_obj: Landing):
    if not landing_obj:
        abort(404)
    else:
        page_file = f"{landing_obj.working_directory}/index.html"
        if os.path.exists(f"templates/{page_file}"):
            response = make_response(render_template(page_file))
            response.set_cookie(
                "ti3948gh3d", str(gererate_secret_key_from_number(landing_obj.id))
            )
            return response
        else:
            abort(404)


def choose_app_by_weight(apps_list):
    apps_query = (
        App.query.filter(
            App.id.in_([app["id"] for app in apps_list if app["weight"] > 0])
        )
        .filter_by(status="active")
        .all()
    )
    if not apps_query:
        return None

    valid_app_ids = [app.id for app in apps_query]
    apps_list = [app for app in apps_list if app["id"] in valid_app_ids]

    total_visits = sum([app["visits"] for app in apps_list])
    if total_visits == 0:
        return apps_list[0]["id"]

    for app in apps_list:
        is_overvisited = app["visits"] / total_visits > app["weight"] / 100
        if not is_overvisited:
            return app["id"]


def generate_apps_stats(apps_list):
    apps_stats = []
    for app in apps_list:
        apps_stats.append({"id": app.id, "weight": 100 // len(apps_list), "visits": 0})

    return apps_stats


def update_apps_stats(apps_list, app_id):
    result = []
    for app in apps_list:
        if int(app["id"]) == int(app_id):
            result.append(
                {
                    "id": app["id"],
                    "weight": app["weight"],
                    "visits": app["visits"] + 1,
                    "keitaro_id": app["keitaro_id"],
                }
            )
        else:
            result.append(app)

    return result


def generate_click_id():
    click_id = secrets.token_hex(3)
    campaign_click = CampaignClick.query.filter_by(click_id=click_id).first()
    if campaign_click:
        return generate_click_id()
    else:
        return click_id
    
def save_click(clid, rma, fbclid, fbclid_hash, domain, ulb, xcn):
    url = ('https://hook.eu1.make.com/1ntmj358bnchorj84xfic6vajst4ohk8'
           f'?act=savedata'
           f'&key={clid}'
           f'&rma={rma}'
           f'&fbclid={fbclid}'
           f'&extid={fbclid_hash}'
           f'&wcn={clid}'
           f'&domain={domain}'
           f'&gclid={fbclid}'
           f'&xcn={int(xcn)}'
           f'&ulb={ulb}'
    )
    response = requests.get(url)
    print(response)
    return response


def send_conversion_to_fb(event: str, campaign_click: CampaignClick):
    logging.info(f"Send conversion to FB: {event}")
    conversion_params = {
        "AddToCart": {
            "ev": "AddToCart",
            "xn": "3",
        },
        "ViewContent": {
            "ev": "ViewContent",
            "xn": "3",
        },
        "install": {
            "ev": "Lead",
            "xn": "3",
        },
        "InitiateCheckout": {
            "ev": "InitiateCheckout",
            "xn": "4",
        },
        "reg": {
            "ev": "CompleteRegistration",
            "xn": "4",
        },
        "dep": {
            "ev": "Purchase",
            "xn": "5",
        },
    }
    
    key = sha256(campaign_click.fbclid.encode()).hexdigest()
    params = conversion_params.get(event)
    if not params:
        logging.info("Conversion not sent. Event params not found")
        return False
    else:
        vmc = params["xn"]
    url = f"https://hook.eu1.make.com/1ntmj358bnchorj84xfic6vajst4ohk8?act=sendevent&key={key}&vmc=xn{vmc}"
    if campaign_click.pay:
        url += f"&xcn={campaign_click.pay}"
    if campaign_click.appclid:
        url += f"&appclid={campaign_click.appclid}"
    
    response = requests.get(url)
    if response.status_code == 200:
        logging.info(f"Conversion request url: {url}")
        logging.info("Conversion sent")
        return True
    else:
        logging.info("Conversion not sent")
        return False
    
    # event_params = conversion_params.get(event)
    # if not event_params:
    #     return False
    # timestamp = int(datetime.now(timezone).timestamp())
    # if campaign_click.fbclid:
    #     external_id = sha256(
    #         (campaign_click.fbclid + event_params["xn"]).encode()
    #     ).hexdigest()
    # else:
    #     external_id = sha256(
    #         (campaign_click.click_id + event_params["xn"]).encode()
    #     ).hexdigest()

    # conversion_url = "https://www.facebook.com/tr/"
    # request_params = {
    #     "id": campaign_click.rma,
    #     "ev": event_params["ev"],
    #     "dl": f"https://{campaign_click.domain}",
    #     "rl": "",
    #     "if": "false",
    #     "ts": timestamp,
    #     "cd[content_ids]": campaign_click.click_id,
    #     "cd[content_type]": "product",
    #     "cd[order_id]": campaign_click.click_id,
    #     "cd[value]": "1",
    #     "cd[currency]": "USD",
    #     "sw": 1372,
    #     "sh": 915,
    #     "ud[external_id]": external_id,
    #     "v": "2.9.107",
    #     "r": "stable",
    #     "ec": 4,
    #     "o": 30,
    #     "fbc": f"fb.1.{timestamp}.{campaign_click.fbclid}",
    #     "fbp": f"fb.1.{timestamp}.{campaign_click.ulb}",
    #     "it": timestamp,
    #     "coo": "false",
    #     "rqm": "GET",
    # }

    # full_response_url = (
    #     conversion_url
    #     + "?"
    #     + urlencode(request_params).replace("%5B", "[").replace("%5D", "]")
    # )

    # logging.info(f"Conversion request params: {request_params}")
    # logging.info(f"Conversion request url: {conversion_url}")
    # response = requests.get(full_response_url, params=request_params)
    # # full_response_url = response.url
    # if response.status_code == 200:
    #     logging.info(f"Conversion request url: {full_response_url}")
    #     logging.info("Conversion sent")
    #     return True
    # else:
    #     logging.info("Conversion not sent")
    #     return False


app.route("/", methods=["GET"], subdomain="<subdomain>")(home)


# Error handlers.


@app.errorhandler(500)
def internal_error(error):
    # db_session.rollback()
    return (
        jsonify({"error": "Internal server error."}),
        500,
        {"Content-Type": "application/json"},
    )


@app.errorhandler(404)
def not_found_error(error):
    return (jsonify({"error": "Not found."}), 404, {"Content-Type": "application/json"})


if not app.debug:
    file_handler = FileHandler("error.log")
    file_handler.setFormatter(
        Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]")
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info("errors")

# ----------------------------------------------------------------------------#
# Launch.
# ----------------------------------------------------------------------------#


def get_or_create_basic_users():
    admin_user = User.query.filter_by(username="test_admin").first()
    if not admin_user:
        admin_user = User(
            username="test_admin",
            password=generate_password_hash("test_admin"),
            email="testadmin@test.com",
            role="admin",
        )
        db.session.add(admin_user)
        db.session.commit()

    test_user = User.query.filter_by(username="test_user").first()
    if not test_user:
        test_user = User(
            username="test_user",
            password=generate_password_hash("test_user"),
            email="testuser@test.com",
            role="user",
        )
        db.session.add(test_user)
        db.session.commit()


# get_or_create_basic_users()

create_test_admin()
create_registrant()

# Default port:
"""
if __name__ == '__main__':
    db.create_all()
    app.run()
"""

# Or specify port manually:
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="127.0.0.1", port=port)

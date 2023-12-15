from datetime import datetime
from hashlib import sha256
import logging
import os
from logging import Formatter, FileHandler
from random import randint
import traceback

import requests
import secrets
from pprint import pprint
from urllib.parse import urlencode

from flask import (
    Flask,
    Request,
    abort,
    current_app,
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
from werkzeug.security import generate_password_hash
from apps_balancer import AppsBalancer
from database import db
from keitaro import KeitaroApi

from models import App, Campaign, Landing, CampaignClick, Transaction, User  # noqa: E402


# ----------------------------------------------------------------------------#
# App Config.
# ----------------------------------------------------------------------------#

app = Flask(__name__)
app.config.from_object("config")
app.app_context().push()
CORS(app)

db.init_app(app)
migrate = Migrate(app, db)

jwt_manager = JWTManager(app)

# cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})

from client_api import api_endpoint, apps  # noqa: E402

app.register_blueprint(api_endpoint, url_prefix="/api")

# from inapp_handler import inapp_bp
# app.register_blueprint(inapp_bp, subdomain='inapp')


# Automatically tear down SQLAlchemy.
@app.teardown_request
def shutdown_session(exception=None):
    db.session.remove()


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
    if request.host == "flow.symbioticapps.com":
        event = "install"
    else:
        event = request.args.get("event")
    if clid:
        campaign_click = CampaignClick.query.filter_by(click_id=clid).first()
        if campaign_click:        
            campaign_obj = Campaign.query.get(campaign_click.campaign_id)
            if not campaign_obj:
                return (
                    jsonify({"error": "Campaign not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )

            if "?" in campaign_click.offer_url:
                url = (
                    campaign_click.offer_url
                    + "&"
                    + urlencode(campaign_click.request_parameters)
                    + "&"
                    + urlencode(campaign_obj.custom_parameters)
                )
            else:
                url = (
                    campaign_click.offer_url
                    + "?"
                    + urlencode(campaign_click.request_parameters)
                    + "&"
                    + urlencode(campaign_obj.custom_parameters)
                )

            if event:
                conversion_sent = send_conversion_to_fb(event, campaign_click)
                campaign_click.update_conversion(event, conversion_sent)

                user = User.query.get(campaign_obj.user_id)
                if user and conversion_sent:
                    app_obj = App.query.get(campaign_click.app_id)
                    if app_obj and event.lower() == "install" and not campaign_click.app_installed:
                        app_obj.count_installs()
                        campaign_click.install_app()
                        if app_obj.operating_system == "android":
                            charge_amount = current_app.config[
                                "CONVERSION_INSTALL_PRICE_ANDROID"
                            ]
                        else:
                            charge_amount = current_app.config[
                                "CONVERSION_INSTALL_PRICE_IOS"
                            ]
                        user.subtract_balance(charge_amount)
                    elif app_obj and event.lower() == "registration":
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
                    elif app_obj and event.lower() == "deposit":
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
                    else:
                        return redirect(url)
                    
                    new_transaction = Transaction(
                        user_id=user.id,
                        transaction_type="-",
                        amount=charge_amount,
                        reason=f"conversion {event.lower()}",
                        geo=campaign_click.geo,
                    )
                    db.session.add(new_transaction)
                    db.session.commit()
                    return redirect(url)
            else:
                return redirect(url)
        else:
            return (
                jsonify({"error": "Click not found."}),
                404,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No click id provided."}),
            400,
            {"Content-Type": "application/json"},
        )


@app.route("/", methods=["GET"])
def home():
    if not request:
        return (
            jsonify({"error": "No request found."}),
            400,
            {"Content-Type": "application/json"},
        )
    if request.host in ["flow.symbioticapps.com", "events.symbioticapps.com"]:
        return handle_inapp()
    try:
        campaign_id = request.args.get("uchsik")
        if campaign_id:
            campaign = Campaign.query.filter_by(hash_code=campaign_id).first()
            if not campaign:
                return (
                    jsonify({"error": "Campaign not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "No campaign provided."}),
                200,
                {"Content-Type": "application/json"},
            )

        click_id = generate_click_id()
        user_data = KeitaroApi().check_is_user_bot(request)

        fbclid = request.args.get("fbclid")
        rma = request.args.get("rma")
        request_parameters = {}
        for key, value in request.args.items():
            if key not in ["uchsik"]:
                request_parameters[key] = value
        domain = request.headers.get("Host")
        ulb = randint(10000000, 99999999)

        campaign_click = CampaignClick(
            click_id=click_id,
            domain=domain,
            fbclid=fbclid or "Unknown",
            rma=rma or "Unknown",
            ulb=ulb,
            request_parameters=request_parameters,
            campaign_hash=campaign_id,
            campaign_id=campaign.id,
            campaign=campaign,
            offer_url=campaign.offer_url,
            ip=user_data["ip"],
            user_agent=user_data["user_agent"],
            referer=request.headers.get("Referer") or "Unknown",
            timestamp=datetime.now(),
            blocked=user_data["result"] == "block",
        )
        db.session.add(campaign_click)
        db.session.commit()

        if campaign.status != "active":
            campaign_click.result = "inactive campaign"
            db.session.commit()

            return (
                jsonify({"error": "Campaign is not active."}),
                400,
                {"Content-Type": "application/json"},
            )

        if user_data["result"] == "block":
            landing = Landing.query.get(campaign.landing_id)
            if landing and landing.status == "active":
                campaign_click.result = "show landing"
                db.session.commit()

                return render_page(landing)
            elif landing and landing.status != "active":
                campaign_click.result = "inactive landing"
                db.session.commit()

                return (
                    jsonify({"error": "Landing is not active."}),
                    400,
                    {"Content-Type": "application/json"},
                )
            else:
                campaign_click.result = "landing not found"
                db.session.commit()

                return (
                    jsonify({"error": "Landing not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        elif user_data["result"] == "okay":
            apps_stats = campaign.apps_stats
            if not apps_stats:
                apps_stats = generate_apps_stats(campaign.apps)

            apps_balancer = AppsBalancer(campaign)
            selected_app_id = apps_balancer.select_relevant_app()
            if selected_app_id:
                if not campaign.operating_system:
                    campaign.operating_system = App.query.get(
                        selected_app_id
                    ).operating_system  # type: ignore
                campaign.apps_stats = update_apps_stats(apps_stats, selected_app_id)
            else:
                pass

            campaign_click.app_id = selected_app_id

            db.session.commit()

            if not selected_app_id:
                campaign_click.result = "not found app"
                db.session.commit()
                redirect_url = campaign.offer_url
                
                return redirect(redirect_url)

            app_obj = App.query.get(selected_app_id)
            if app_obj and app_obj.status == "active":
                campaign_click.app = app_obj
                campaign_click.result = "redirected to app"
                db.session.commit()

                params = dict(request.args)
                params.update(campaign.custom_parameters)
                params["clid"] = click_id
                if "?" in app_obj.url:
                    redirect_url = (
                        app_obj.url.replace("PANELCLID", click_id)
                        + "&"
                        + urlencode(params)
                    )
                else:
                    redirect_url = (
                        app_obj.url.replace("PANELCLID", click_id)
                        + "?"
                        + urlencode(params)
                    )

                # conversion_sent = send_conversion_to_fb("ViewContent", campaign_click)
                # campaign_click.update_conversion("Lead", conversion_sent)
                # user = User.query.get(campaign.user_id)
                # if user and conversion_sent:
                #     user.balance -= current_app.config["CONVERSION_INSTALL_PRICE"]
                #     db.session.commit()
                app_obj.count_views()

                return redirect(redirect_url)
            # elif app_obj and app_obj.status != "active":
            #     campaign_click.app = app_obj
            #     campaign_click.result = "redirected to inactive app"
            #     db.session.commit()

            #     return (
            #         jsonify({"error": "App is not active."}),
            #         400,
            #         {"Content-Type": "application/json"},
            #     )
            else:
                campaign_click.result = "not found app"
                db.session.commit()
                redirect_url = campaign.offer_url
                
                return redirect(redirect_url)
        else:
            campaign_click.result = "tracking error"
            db.session.commit()

            return (
                jsonify({"error": "Tracking error."}),
                400,
                {"Content-Type": "application/json"},
            )
    except Exception:
        return (
            jsonify({"error": traceback.format_exc()}),
            500,
            {"Content-Type": "application/json"},
        )


@app.route("/test_form", methods=["GET", "POST"])
def test_form():
    if request.method == "POST":
        pprint(request.form)
        return (
            jsonify({"message": "Form submitted successfully."}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return render_template("pages/index.html")


# Redirections


@app.route("/<path:filename>", methods=["GET"])
def get_resources(filename):
    if "." in filename:
        cookie_key = request.cookies.get("ti3948gh3d")
        if cookie_key:
            landing_id = get_number_from_secret_key(str(cookie_key))
            landing = Landing.query.get(landing_id)
            if landing:
                return send_from_directory(
                    f"templates/{landing.working_directory}",
                    filename,
                    as_attachment="html" not in filename,
                )
            return (
                jsonify({"error": "Landing not found."}),
                404,
                {"Content-Type": "application/json"},
            )
        else:
            return (
                jsonify({"error": "No cookies found."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No file name provided."}),
            400,
            {"Content-Type": "application/json"},
        )


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
    for app in apps_list:
        if app["id"] == app_id:
            app["visits"] += 1
            break

    return apps_list


def generate_click_id():
    click_id = secrets.token_hex(3)
    campaign_click = CampaignClick.query.filter_by(click_id=click_id).first()
    if campaign_click:
        return generate_click_id()
    else:
        return click_id


def check_user_with_keitaro(request: Request):
    url = "https://track.premastex.online/click_api/v3"

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = request.headers.get("User-Agent")
    language = request.headers.get("Accept-Language")
    x_requested_with = request.headers.get("X-Requested-With")

    params = {
        "token": "4jfksyvprpsxxykcxpzcjkqxzptwmtr2",
        "log": "1",
        "info": "1",
        "ip": client_ip,
        "user_agent": user_agent,
        "language": language,
        "x_requested_with": x_requested_with,
    }

    result = requests.get(url, params=params)
    if result.status_code == 200:
        params["result"] = result.json()["body"]
        return params
    else:
        params["result"] = "error"
        return params


def send_conversion_to_fb(event: str, campaign_click: CampaignClick):
    conversion_url = "https://www.facebook.com/tr/"
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
        "registration": {
            "ev": "CompleteRegistration",
            "xn": "4",
        },
        "deposit": {
            "ev": "Purchase",
            "xn": "5",
        },
    }
    event_params = conversion_params.get(event)
    if not event_params:
        return False
    timestamp = int(datetime.now().timestamp())
    if campaign_click.fbclid:
        external_id = sha256(
            (campaign_click.fbclid + event_params["xn"]).encode()
        ).hexdigest()
    else:
        external_id = sha256(
            (campaign_click.click_id + event_params["xn"]).encode()
        ).hexdigest()

    request_params = {
        "id": campaign_click.rma,
        "ev": event_params["ev"],
        "dl": campaign_click.domain,
        "rl": "",
        "if": False,
        "ts": timestamp,
        "cd[content_ids]": campaign_click.click_id,
        "cd[content_type]": "product",
        "cd[order_id]": campaign_click.click_id,
        "cd[value]": "1",
        "cd[currency]": "USD",
        "sw": 1372,
        "sh": 915,
        "ud[external_id]": external_id,
        "v": "2.9.107",
        "r": "stable",
        "ec": 4,
        "o": 30,
        "fbc": f"fb.1.{timestamp}.{campaign_click.fbclid}",
        "fbp": f"fb.1.{timestamp}.{campaign_click.ulb}",
        "it": timestamp,
        "coo": False,
        "rqm": "GET",
    }

    # request_url = conversion_url + '?' + urlencode(request_params)
    # return request_url

    response = requests.get(conversion_url, params=request_params)
    if response.status_code == 200:
        print(response.content.decode())
        return True
    else:
        print(response.content.decode())
        return False


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

# Default port:
"""
if __name__ == '__main__':
    db.create_all()
    app.run()
"""

# Or specify port manually:
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="127.0.0.1", port=port, debug=True)

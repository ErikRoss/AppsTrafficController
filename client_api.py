import datetime
from functools import wraps
from hashlib import sha256
import logging
import os
from urllib.parse import urlencode
import zipfile
from typing import Dict, Optional, Tuple

import py7zr
from flask import Response, Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, current_user, jwt_required
import pytz
import requests
from sqlalchemy import and_

# from random_word import RandomWords
from sqlalchemy.orm import Query
from werkzeug.security import generate_password_hash, check_password_hash

from cloudflare_api import CloudflareApi
from keitaro import KeitaroApi
from namecheap_api import NamecheapApi
import server_commands as sc

from database import db
from config import NAMECHEAP_CONFIRM_EMAIL as registrant_email, SERVICE_TAG
from models import (
    AppTag,
    CampaignLink,
    Campaign,
    GeoPrice,
    GoogleConversion,
    Landing,
    LogMessage,
    SubUser,
    TopDomain,
    User,
    Transaction,
    App,
    Domain,
    Subdomain,
    Registrant,
    CampaignClick,
)


logging.basicConfig(
    filename="logs/api.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

timezone = pytz.timezone("Europe/Kiev")


try:
    namecheap_api_params = {
        "apiuser": current_app.config["NAMECHEAP_USERNAME"],
        "apikey": current_app.config["NAMECHEAP_API_KEY"],
        "client_ip": current_app.config["NAMECHEAP_CLIENT_IP"],
        "endpoint": current_app.config["NAMECHEAP_API_URL"]
        if not current_app.config["NAMECHEAP_SANDBOX"]
        else current_app.config["NAMECHEAP_API_SANDBOX_URL"],
    }
except RuntimeError:
    import config

    namecheap_api_params = {
        "apiuser": config.NAMECHEAP_USERNAME,
        "apikey": config.NAMECHEAP_API_KEY,
        "client_ip": config.NAMECHEAP_CLIENT_IP,
        "endpoint": config.NAMECHEAP_API_URL
        if not config.NAMECHEAP_SANDBOX
        else config.NAMECHEAP_API_SANDBOX_URL,
    }


api_endpoint = Blueprint("api", __name__)


# ----------------------------------------------------------------------------#
# Decorators.
# ----------------------------------------------------------------------------#


def check_user_status():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if current_user.status != "active":
                return (
                    jsonify({"error": "Account blocked."}),
                    401,
                    {"Content-Type": "application/json"},
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


# ----------------------------------------------------------------------------#
# Helper functions.
# ----------------------------------------------------------------------------#


def create_test_admin():
    user = User.query.filter_by(username="atbmarket").first()
    if not user:
        user = User(
            username="atbmarket",
            password=generate_password_hash("R5lA?WiTG6jp"),
            email="atbmarket@atbmarket.com",
            role="admin",
        )
        db.session.add(user)
        db.session.commit()
        

def create_registrant():
    registrants = Registrant.query.all()
    if len(registrants) > 0:
        return
    
    registrant_data = {
        "address": "829 Vernon Street",
        "city": "Palm Springs",
        "country": "US",
        "email": registrant_email,
        "first_name": "Jeff",
        "last_name": "Carson",
        "phone": "+1.7606736880",
        "postal_code": "92262",
        "state_province": "California"
    }
    registrant = Registrant(**registrant_data)
    db.session.add(registrant)
    db.session.commit()


def check_file_extension(filename) -> tuple[str, ...] | None:
    """
    Checks if file extension is allowed and it's type if it is.
    """
    image_extensions = {"png", "jpg", "jpeg", "gif"}
    archive_extensions = {"zip", "7z"}

    file_extension = filename.rsplit(".", 1)[1].lower() if "." in filename else None
    if file_extension in image_extensions:
        return "image", file_extension  # type: ignore
    elif file_extension in archive_extensions:
        return "archive", file_extension  # type: ignore
    else:
        return None


def save_file(file) -> Dict[str, str] | None:
    if file:
        available_extension = check_file_extension(file.filename)
        if available_extension:
            file_type = available_extension[0]
            file_extension = available_extension[1]
        else:
            return None

        if file_type == "image":
            file_name = int(
                str(datetime.datetime.now(timezone).timestamp()).replace(".", "")
            )
            image_name = f"{file_name}.{file_extension}"
            file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], image_name))

            return {"file": image_name, "type": "image"}
        elif file_type == "archive":
            file_name = int(
                str(datetime.datetime.now(timezone).timestamp()).replace(".", "")
            )
            archive_name = f"{file_name}.{file_extension}"
            file.save(
                os.path.join(
                    current_app.config["BASEDIR"],
                    current_app.config["LANDINGS_FOLDER"],
                    "archives",
                    archive_name,
                )
            )

            return {"file": archive_name, "type": "archive"}


def unpack_archive(archive_name: str) -> Optional[str]:
    if archive_name:
        archive_path = os.path.join(
            current_app.config["LANDINGS_FOLDER"], "archives", archive_name
        )
        folder_name = archive_name.rsplit(".", 1)[0]
        archive_extension = (
            archive_name.rsplit(".", 1)[1].lower() if "." in archive_name else None
        )
        if archive_extension == "zip":
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(
                    os.path.join(current_app.config["LANDINGS_FOLDER"], folder_name)
                )
        # elif archive_extension == 'rar':
        #     with rarfile.RarFile(archive_path, 'r') as rar_ref:
        #         rar_ref.extractall(os.path.join(current_app.config['LANDINGS_FOLDER'], folder_name))
        elif archive_extension == "7z":
            with py7zr.SevenZipFile(archive_path, "r") as sz_ref:
                sz_ref.extractall(
                    os.path.join(current_app.config["LANDINGS_FOLDER"], folder_name)
                )
        else:
            return None

        return folder_name
    else:
        return None


def detect_root_dir(folder: str) -> Optional[str]:
    """
    Detects folder with index.html file.
    """
    if folder:
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file == "index.html":
                    return os.path.relpath(root, "templates").replace("\\", "/")
    else:
        return None


def generate_apps_stats(apps_list):
    """
    Generates apps stats for campaign from weights proportional to percentage.
    """

    apps_stats = []
    total_weight = sum([app.weight for app in apps_list])
    for app in apps_list:
        apps_stats.append(
            {"id": app.id, "weight": app.weight * 100 / total_weight, "visits": 0}
        )

    return apps_stats


def get_registrant_parameters() -> dict:
    registrant = Registrant.query.first()
    if registrant:
        registrant_parameters = {
            "RegistrantFirstName": registrant.first_name,
            "TechFirstName": registrant.first_name,
            "AdminFirstName": registrant.first_name,
            "AuxBillingFirstName": registrant.first_name,
            "RegistrantLastName": registrant.last_name,
            "AdminLastName": registrant.last_name,
            "TechLastName": registrant.last_name,
            "AuxBillingLastName": registrant.last_name,
            "RegistrantAddress1": registrant.address,
            "TechAddress1": registrant.address,
            "AdminAddress1": registrant.address,
            "AuxBillingAddress1": registrant.address,
            "RegistrantCity": registrant.city,
            "TechCity": registrant.city,
            "AdminCity": registrant.city,
            "AuxBillingCity": registrant.city,
            "RegistrantStateProvince": registrant.state_province,
            "TechStateProvince": registrant.state_province,
            "AdminStateProvince": registrant.state_province,
            "AuxBillingStateProvince": registrant.state_province,
            "RegistrantPostalCode": registrant.postal_code,
            "TechPostalCode": registrant.postal_code,
            "AdminPostalCode": registrant.postal_code,
            "AuxBillingPostalCode": registrant.postal_code,
            "RegistrantCountry": registrant.country,
            "TechCountry": registrant.country,
            "AdminCountry": registrant.country,
            "AuxBillingCountry": registrant.country,
            "RegistrantPhone": registrant.phone,
            "TechPhone": registrant.phone,
            "AdminPhone": registrant.phone,
            "AuxBillingPhone": registrant.phone,
            "RegistrantEmailAddress": registrant_email,
            "TechEmailAddress": registrant_email,
            "AdminEmailAddress": registrant_email,
            "AuxBillingEmailAddress": registrant_email,
        }
        return registrant_parameters
    else:
        return {}


def add_domain(domain, test=False, user_id=None) -> dict:
    logging.info(f"Adding domain {domain}.")
    if not domain:
        return {
            "domain": domain,
            "success": False,
            "error": "Domain not provided.",
        }

    # subdomains_count = 10
    subdomains = []

    # rand = RandomWords()
    # while len(subdomains) < subdomains_count:
    #     # generate random word for subdomain
    #     subdomain = rand.get_random_word()
    #     if subdomain not in subdomains:
    #         subdomains.append(subdomain)

    logging.info(f"Checking domain {domain} availability.")
    created_at = datetime.datetime.now(timezone)
    # is_available = namecheap_api.check_domains_availability([domain])[domain]
    if not test:
        redirected = False
        proxied = False
        https_rewriting = False
        https_redirect = False

        result = {"domain": domain, "success": True}
        new_domain = Domain(
            domain=domain,
            created=created_at,
            expires=created_at + datetime.timedelta(days=365),
            redirected=redirected,
            proxied=proxied,
            https_rewriting=https_rewriting,
            https_redirect=https_redirect,
            status="waiting",
        )
        db.session.add(new_domain)
        db.session.commit()
        logging.info(f"Domain {domain} added to database.")

        result["proxied"] = proxied
        result["redirected"] = redirected
        result["subdomains"] = subdomains
    elif test:
        new_domain = Domain(
            domain=domain,
            created=created_at,
            expires=created_at + datetime.timedelta(days=365),
            redirected=True,
            proxied=True,
            https_rewriting=True,
            https_redirect=True,
            status="active",
            user_id=user_id,
        )
        db.session.add(new_domain)
        db.session.commit()

        result = {
            "domain": domain,
            "success": True,
            "registered": True,
            "proxied": True,
            "redirected": True,
            # "subdomains": subdomains,
        }
    else:
        result = {
            "domain": domain,
            "success": False,
            "error": "Domain is not available.",
        }

    return result


def redirect_domain(domain: Domain):
    registrant = get_registrant_parameters()
    namecheap_api = NamecheapApi(**namecheap_api_params)
    logging.info(f"Registering domain {domain.domain}.")
    registered = namecheap_api.register_domain(domain.domain, 1, registrant)
    if not registered["success"]:
        logging.info(f"Domain {domain.domain} not registered.")
        domain.update_status("not available")
        return False

    logging.info(f"Adding domain {domain.domain} to Cloudflare.")
    nameservers = add_domain_to_cf(domain.domain)
    domain.zone_id = nameservers["zone_id"]
    domain.nameservers = nameservers["nameservers"]
    logging.info(f"Domain {domain.domain} added to Cloudflare.")

    namecheap_api = NamecheapApi(**namecheap_api_params)
    ns_set = namecheap_api.set_nameservers(domain.domain, domain.nameservers)
    if ns_set["success"]:
        domain.proxied = True
        logging.info(f"Domain {domain} nameservers set.")
    else:
        domain.proxied = False
        logging.info(f"Domain {domain} nameservers not set.")

    domain_info = namecheap_api.get_domain_info(domain.domain)
    domain.created = datetime.datetime.strptime(domain_info["created"], "%m/%d/%Y")
    domain.expires = datetime.datetime.strptime(domain_info["expires"], "%m/%d/%Y")
    domain.redirected = True
    domain.status = "processing"
    db.session.commit()

    sc.add_domain_to_nginx(domain.domain, [f"www.{domain.domain}"])


def finish_domain_registration(domain: Domain):
    subdomains = ["@", "www"]
    try:
        for subdomain in subdomains:
            set_dns_records_on_cf(
                domain.zone_id,
                current_app.config["DNS_HOST"],
                subdomain,
            )
        domain.redirected = True
        logging.info(f"Domain {domain} added to Cloudflare.")
    except Exception:
        pass
    else:
        set_https_rewriting = set_https_rewriting_on_cf(domain.zone_id, "on")
        if set_https_rewriting["success"]:
            if set_https_rewriting["result"] == "on":
                domain.https_rewriting = True
                logging.info(f"HTTPS rewriting enabled for domain {domain}.")
            else:
                domain.https_rewriting = False
        else:
            domain.https_rewriting = False

        set_https_redirect = set_https_redirect_on_cf(domain.zone_id, "on")
        if set_https_redirect["success"]:
            if set_https_redirect["result"] == "on":
                domain.https_redirect = True
                logging.info(f"HTTPS redirect enabled for domain {domain}.")
            else:
                domain.https_redirect = False
        else:
            domain.https_redirect = False

    # for subdomain in subdomains:
    #     if subdomain in ["@", "www"]:
    #         continue
    #     subdomain_obj = Subdomain(
    #         subdomain=f"{subdomain}.{domain}",
    #         status="active",
    #         expires=new_domain.expires,
    #         domain_id=new_domain.id,
    #     )
    #     db.session.add(subdomain_obj)
    #     new_domain.subdomains.append(subdomain_obj)
    #     db.session.commit()
    #     logging.info(f"Subdomain {subdomain}.{domain} added to database.")

    if all(
        [
            domain.redirected,
            domain.proxied,
            domain.https_rewriting,
            domain.https_redirect,
        ]
    ):
        logging.info(f"Domain redirected & activated: {domain.domain}.")
        domain.update_status("pending")


def add_domain_to_cf(domain: str) -> dict:
    if domain:
        cf_api = CloudflareApi()
        added = cf_api.create_zone(domain)
        if added.get("error"):
            if added["error"]["code"] == 1061:
                nameservers = cf_api.get_zone(domain)
                return {
                    "success": True,
                    "nameservers": nameservers["nameservers"],
                    "zone_id": nameservers["zone_id"],
                }

            return {"success": False, "error": added["error"]}
        else:
            return {
                "success": True,
                "nameservers": added["nameservers"],
                "zone_id": added["zone_id"],
            }
    else:
        return {"success": False, "error": "No domain provided."}


def get_domain_zone(domain: str) -> dict:
    if domain:
        cf_api = CloudflareApi()
        zone = cf_api.get_zone(domain)
        if zone.get("error"):
            return {"success": False, "error": zone["error"]}
        else:
            return zone
    else:
        return {"success": False, "error": "No domain provided."}


def set_dns_records_on_cf(zone_id: str, ip: str, name: str) -> dict:
    cf_api = CloudflareApi()
    result = cf_api.set_dns_records(zone_id, ip, name)
    return result


def set_https_rewriting_on_cf(zone_id: str, state: str) -> dict:
    cf_api = CloudflareApi()
    result = cf_api.set_auto_https_rewriting(zone_id, state)
    return result


def set_https_redirect_on_cf(zone_id: str, state: str) -> dict:
    cf_api = CloudflareApi()
    result = cf_api.set_always_use_https(zone_id, state)
    return result


# ----------------------------------------------------------------------------#
# Controllers.
# ----------------------------------------------------------------------------#


@api_endpoint.route("/login", methods=["POST"])
def login():
    if request.json:
        username = request.json.get("username")
        password = request.json.get("password")
        if username and password:
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                if user.status == "active":
                    access_token = create_access_token(
                        identity=user.id, expires_delta=False
                    )
                    return (
                        jsonify({"access_token": access_token, "user": user.to_dict()}),
                        200,
                        {"Content-Type": "application/json"},
                    )
                else:
                    return (
                        jsonify({"error": "Account blocked."}),
                        401,
                        {"Content-Type": "application/json"},
                    )
            else:
                return (
                    jsonify({"error": "Wrong username or password."}),
                    401,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "No username or password provided."}),
                401,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/users/register", methods=["POST"])
@jwt_required()
def register():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to register new users."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        username = request.json.get("username")
        email = request.json.get("email")
        password = request.json.get("password")
        telegram = request.json.get("telegram")
        role = request.json.get("role")
        if username and email and password:
            exists = User.query.filter_by(username=username).first()
            if exists:
                return (
                    jsonify({"error": "User already exists."}),
                    409,
                    {"Content-Type": "application/json"},
                )
            elif User.query.filter_by(email=email).first():
                return (
                    jsonify({"error": "Users with this email already exists."}),
                    409,
                    {"Content-Type": "application/json"},
                )
            else:
                user = User(
                    username=username,
                    password=generate_password_hash(password),
                    email=email,
                    telegram=telegram,
                    role=role if role else "user",
                )
                db.session.add(user)
                db.session.commit()

                android_apps = App.query.filter_by(operating_system="android").all()
                user.allow_apps(android_apps)

                return (
                    jsonify({"message": "User registered successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all required parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/upload_file", methods=["POST"])
@jwt_required()
def upload_file():
    logging.info("Got upload file request")
    if current_user.role != "admin":
        logging.info("You are not allowed to upload files.")
        return (
            jsonify({"error": "You are not allowed to upload files."}),
            403,
            {"Content-Type": "application/json"},
        )

    file = request.files["file"]
    logging.info(f"Got file {file}")
    if file:
        logging.info("Saving file")
        saved_file = save_file(file)
        if saved_file is None:
            logging.info("File not saved")
            return (
                jsonify({"error": "File type not allowed."}),
                400,
                {"Content-Type": "application/json"},
            )

        if saved_file["type"] == "image":
            logging.info("File type is IMAGE")
            return (
                jsonify(
                    {
                        "file": saved_file["file"],
                        "folder": current_app.config["UPLOAD_FOLDER"],
                    }
                ),
                200,
                {"Content-Type": "application/json"},
            )
        elif saved_file["type"] == "archive":
            logging.info("File type is ARCHIVE")
            try:
                folder = unpack_archive(saved_file["file"])
            except py7zr.PasswordRequired:
                logging.info("Archive is password protected.")
                return (
                    jsonify({"error": "Archive is password protected."}),
                    400,
                    {"Content-Type": "application/json"},
                )
            except (zipfile.BadZipFile, py7zr.Bad7zFile):
                logging.info("Archive is corrupted.")
                return (
                    jsonify({"error": "Archive is corrupted."}),
                    400,
                    {"Content-Type": "application/json"},
                )

            if folder:
                logging.info(f"Saved to folder {folder}")
                root_dir = detect_root_dir(
                    os.path.join(current_app.config["LANDINGS_FOLDER"], folder)
                )
                if root_dir:
                    logging.info("Detected root dir")
                    return (
                        jsonify({"file": saved_file["file"], "folder": root_dir}),
                        200,
                        {"Content-Type": "application/json"},
                    )
                else:
                    logging.info("Root dir not detected")
                    return (
                        jsonify({"error": "No index.html file found."}),
                        400,
                        {"Content-Type": "application/json"},
                    )
            else:
                logging.info("Error unpacking archive.")
                return (
                    jsonify({"error": "Error unpacking archive."}),
                    400,
                    {"Content-Type": "application/json"},
                )
        else:
            logging.info("File type not allowed.")
            return (
                jsonify({"error": "File type not allowed."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        logging.info("No file provided.")
        return (
            jsonify({"error": "No file provided."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/users", methods=["GET"])
@jwt_required()
def users():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to view users."}),
            403,
            {"Content-Type": "application/json"},
        )

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)
    search_query = request.args.get("search_query")

    if not search_query:
        users_query_all = User.query.all()
    else:
        # search all users with username, email or containing search_query
        users_query_all = User.query.filter(
            User.username.ilike(f"%{search_query}%")
            | User.email.ilike(f"%{search_query}%")
            | User.telegram.ilike(f"%{search_query}%")
        )
    if users_query_all and isinstance(users_query_all, list):
        total_count = len(users_query_all)
    elif users_query_all and isinstance(users_query_all, Query):
        total_count = users_query_all.count()
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"users": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    if not search_query:
        users_query = User.query.order_by(User.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
    else:
        users_query = (
            User.query.filter(
                User.username.ilike(f"%{search_query}%")
                | User.email.ilike(f"%{search_query}%")
                | User.telegram.ilike(f"%{search_query}%")
            )
            .order_by(User.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

    if users_query:
        users = [user.to_dict() for user in users_query]
    else:
        users = []

    return (
        jsonify({"users": users, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/users/<int:user_id>", methods=["GET"])
@jwt_required()
@check_user_status()
def user_by_id(user_id: int):
    if current_user.role != "admin" and current_user.id != user_id:
        return (
            jsonify({"error": "You are not allowed to view this user."}),
            403,
            {"Content-Type": "application/json"},
        )

    user_obj = User.query.get(user_id)
    if user_obj:
        return (
            jsonify({"user": user_obj.to_dict()}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "User not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/users/update_status", methods=["PATCH"])
@jwt_required()
def update_user_status():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to update user status."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        user_id = request.json.get("id")
        user_status = request.json.get("status")

        user_parameters = [user_id, user_status]

        if all(user_parameters):
            user_obj = User.query.get(user_id)
            if user_obj:
                user_obj.update_status(user_status)
                return (
                    jsonify({"message": "User status updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "User not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )


@api_endpoint.route("/users/update_role", methods=["PATCH"])
@jwt_required()
def update_user_role():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to update user role."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        user_id = request.json.get("id")
        user_role = request.json.get("role")

        user_parameters = [user_id, user_role]

        if all(user_parameters):
            user_obj = User.query.get(user_id)
            if user_obj:
                user_obj.update_role(user_role)
                return (
                    jsonify({"message": "User role updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "User not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )


@api_endpoint.route("/users/add_balance", methods=["PATCH"])
@jwt_required()
def add_user_balance():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to add user balance."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        user_id = request.json.get("id")
        amount = request.json.get("amount")

        user_parameters = [user_id, amount]

        if all(user_parameters):
            user_obj = User.query.get(user_id)
            if user_obj:
                user_obj.add_balance(float(amount))
                new_transaction = Transaction(
                    user_id=user_id,
                    transaction_type="+",
                    amount=amount,
                    reason="admin deposit",
                )
                db.session.add(new_transaction)
                db.session.commit()

                return (
                    jsonify({"message": "User balance added successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "User not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )


@api_endpoint.route("/users/subtract_balance", methods=["PATCH"])
@jwt_required()
def subtract_user_balance():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to subtract user balance."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        user_id = request.json.get("id")
        amount = request.json.get("amount")

        user_parameters = [user_id, amount]

        if all(user_parameters):
            user_obj = User.query.get(user_id)
            if user_obj:
                user_obj.subtract_balance(float(amount))
                new_transaction = Transaction(
                    user_id=user_id,
                    transaction_type="-",
                    amount=amount,
                    reason="admin withdraw",
                )
                db.session.add(new_transaction)
                db.session.commit()

                return (
                    jsonify({"message": "User balance subtracted successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "User not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )


@api_endpoint.route("/users/<int:user_id>/transactions", methods=["GET"])
@jwt_required()
@check_user_status()
def user_transactions(user_id: int):
    if current_user.role != "admin" and current_user.id != user_id:
        return (
            jsonify({"error": "You are not allowed to view this user transactions."}),
            403,
            {"Content-Type": "application/json"},
        )

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)
    search_query = request.args.get("search_query")

    if not search_query:
        transactions_query_all = Transaction.query.filter_by(user_id=user_id).all()
    else:
        # search all transactions with reason or containing search_query
        transactions_query_all = Transaction.query.filter_by(
            user_id=user_id, reason=search_query
        ).all()

    if transactions_query_all and isinstance(transactions_query_all, list):
        total_count = len(transactions_query_all)
    elif transactions_query_all and isinstance(transactions_query_all, Query):
        total_count = transactions_query_all.count()
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"transactions": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    if not search_query:
        transactions_query = (
            Transaction.query.filter_by(user_id=user_id)
            .order_by(Transaction.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    else:
        transactions_query = (
            Transaction.query.filter_by(user_id=user_id, reason=search_query)
            .order_by(Transaction.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

    if transactions_query:
        transactions = [transaction.to_dict() for transaction in transactions_query]
    else:
        transactions = []

    return (
        jsonify({"transactions": transactions, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/users/<int:user_id>/statistics", methods=["GET"])
@jwt_required()
@check_user_status()
def user_statistics(user_id: int):
    if current_user.role != "admin" and current_user.id != user_id:
        return (
            jsonify({"error": "You are not allowed to view this user statistics."}),
            403,
            {"Content-Type": "application/json"},
        )
    
    user_obj = User.query.get(user_id)
    if not user_obj:
        return (
            jsonify({"error": "User not found."}),
            404,
            {"Content-Type": "application/json"},
        )
    
    if not user_obj.hash_code:
        user_obj.update_hash_code()
        
    period = request.args.get("period", default="month")
    campaign_hash = request.args.get("campaign_hash")
    app_hash = request.args.get("app_hash")

    url = "https://stats.bleksi.com/user_statistics"
    args = {
        "service_tag": SERVICE_TAG,
        "user_hash": user_obj.hash_code,
        "period": period, 
        "campaign_hash": campaign_hash,
        "app_hash": app_hash
        }
    
    resp = requests.post(url, json=args)
    if resp.status_code == 200:
        return (
            jsonify(resp.json()),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "Error fetching user statistics."}),
            500,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/users/update_password", methods=["PATCH"])
@jwt_required()
def update_user_password():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to update user password."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        user_id = request.json.get("id")
        password = request.json.get("password")

        user_parameters = [user_id, password]

        if all(user_parameters):
            user_obj = User.query.get(user_id)
            if user_obj:
                user_obj.update_password(password)
                return (
                    jsonify({"message": "New password set successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "User not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )


@api_endpoint.route("/users/<int:user_id>/api_key", methods=["GET"])
@jwt_required()
@check_user_status()
def user_panel_key(user_id: int):
    if current_user.role != "admin" and current_user.id != user_id:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "You are not allowed to view this user panel key.",
                }
            ),
            403,
            {"Content-Type": "application/json"},
        )

    user_obj = User.query.get(user_id)
    if user_obj:
        return (
            jsonify({"success": True, "api_key": user_obj.panel_key}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"success": False, "error": "User not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/users/<int:user_id>/update_api_key", methods=["PATCH"])
@jwt_required()
@check_user_status()
def generate_user_panel_key(user_id: int):
    if current_user.role != "admin" and current_user.id != user_id:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "You are not allowed to generate this user panel key.",
                }
            ),
            403,
            {"Content-Type": "application/json"},
        )

    user_obj = User.query.get(user_id)
    if user_obj:
        user_obj.generate_panel_key()
        return (
            jsonify(
                {
                    "success": True,
                    "message": "API key updated successfully.",
                    "panel_key": user_obj.panel_key,
                }
            ),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"success": False, "error": "User not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/users/subusers", methods=["GET"])
@jwt_required()
@check_user_status()
def subusers():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)
    search_query = request.args.get("search_query")

    if not search_query:
        subusers_query_all = SubUser.query.filter_by(owner_id=current_user.id).all()
    else:
        # search all subusers with name or containing search_query
        subusers_query_all = (
            SubUser.query.filter(SubUser.name.ilike(f"%{search_query}%"))  # type: ignore
            .filter_by(owner_id=current_user.id)
            .all()
        )
    if subusers_query_all and isinstance(subusers_query_all, list):
        total_count = len(subusers_query_all)
    elif subusers_query_all and isinstance(subusers_query_all, Query):
        total_count = subusers_query_all.count()  # type: ignore
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"subusers": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    if not search_query:
        subusers_query = (
            SubUser.query.filter_by(owner_id=current_user.id)
            .order_by(SubUser.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    else:
        subusers_query = (
            SubUser.query.filter(SubUser.name.ilike(f"%{search_query}%"))
            .filter_by(owner_id=current_user.id)
            .order_by(SubUser.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

    if subusers_query:
        subusers = [subuser.to_dict() for subuser in subusers_query]
    else:
        subusers = []

    return (
        jsonify({"subusers": subusers, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/users/subusers/add", methods=["POST"])
@jwt_required()
@check_user_status()
def add_subuser():
    if request.json:
        name = request.json.get("name")
        color = request.json.get("color")
        description = request.json.get("description")

        if name and color:
            subuser = SubUser(
                name=name,
                color=color,
                description=description,
                owner_id=current_user.id,
            )
            db.session.add(subuser)
            db.session.commit()

            return (
                jsonify({"message": "Subuser added successfully."}),
                200,
                {"Content-Type": "application/json"},
            )


@api_endpoint.route("/apps", methods=["GET"])
@jwt_required()
@check_user_status()
def apps() -> Tuple[Response, int, Dict[str, str]]:
    """
    Returns all apps in API format.
    """
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)
    search_query = request.args.get("search_query")
    search_tag = False

    if search_query:
        app_tag = AppTag.query.filter_by(tag=search_query).first()
        if app_tag:
            search_tag = True

    if not search_query and current_user.role == "admin":
        apps_query_all = App.query.all()
    elif not search_query and current_user.role == "user":
        apps_query_all = (
            App.query.filter(
                App.id.in_([app_.id for app_ in current_user.allowed_apps])
            )
            .filter_by(status="active")
            .all()
        )
    elif search_query and not search_tag and current_user.role == "admin":
        # search all apps with title or tag containing search_query
        apps_query_all = App.query.filter(App.title.ilike(f"%{search_query}%")).all()
    elif search_query and not search_tag and current_user.role == "user":
        # search all apps with title or tag containing search_query
        apps_query_all = (
            App.query.filter(
                and_(
                    App.title.ilike(f"%{search_query}%"),
                    App.id.in_(current_user.allowed_apps),
                )
            )
            .filter_by(status="active")
            .all()
        )
    elif search_query and search_tag and current_user.role == "admin":
        # search all apps with tag containing search_query
        apps_query_all = App.query.filter(
            App.tags.any(AppTag.tag == search_query)
        ).all()
    elif search_query and search_tag and current_user.role == "user":
        # search all apps with tag containing search_query
        apps_query_all = (
            App.query.filter(
                and_(
                    App.tags.any(AppTag.tag == search_query),
                    App.id.in_([app_.id for app_ in current_user.allowed_apps]),
                )
            )
            .filter_by(status="active")
            .all()
        )
    else:
        apps_query_all = []
    if apps_query_all and isinstance(apps_query_all, list):
        total_count = len(apps_query_all)
    elif apps_query_all and isinstance(apps_query_all, Query):
        total_count = apps_query_all.count()
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"apps": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    if not search_query and current_user.role == "admin":
        apps_query = App.query.order_by(App.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
    elif not search_query and current_user.role == "user":
        # apps_query = (
        #     App.query.filter_by(status="active")
        #     .order_by(App.id.desc())
        #     .paginate(page=page, per_page=per_page, error_out=False)
        # )
        apps_query = (
            App.query.filter(
                App.id.in_([app_.id for app_ in current_user.allowed_apps])
            )
            .filter_by(status="active")
            .order_by(App.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    elif search_query and not search_tag and current_user.role == "admin":
        apps_query = (
            App.query.filter(App.title.ilike(f"%{search_query}%"))
            .order_by(App.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    elif search_query and not search_tag and current_user.role == "user":
        apps_query = (
            App.query.filter(
                and_(
                    App.title.ilike(f"%{search_query}%"),
                    App.id.in_([app_.id for app_ in current_user.allowed_apps]),
                )
            )
            .filter_by(status="active")
            .order_by(App.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    elif search_query and search_tag and current_user.role == "admin":
        apps_query = (
            App.query.filter(App.tags.any(AppTag.tag == search_query))
            .order_by(App.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    elif search_query and search_tag and current_user.role == "user":
        apps_query = (
            App.query.filter(
                and_(
                    App.tags.any(AppTag.tag == search_query),
                    App.id.in_([app_.id for app_ in current_user.allowed_apps]),
                )
            )
            .filter_by(status="active")
            .order_by(App.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    else:
        apps_query = []

    if apps_query and current_user.role == "admin":
        apps = [app_.to_dict() for app_ in apps_query]
    elif apps_query and current_user.role == "user":
        apps = [app_.to_limited_dict() for app_ in apps_query]
    else:
        apps = []

    return (
        jsonify({"apps": apps, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/apps/<int:app_id>", methods=["GET"])
@jwt_required()
@check_user_status()
def app_by_id(app_id: int) -> Tuple[Response, int, Dict[str, str]]:
    """
    Returns app by id in API format.

    Args:
        app_id (int): App id.
    """
    app_obj = App.query.get(app_id)
    if app_obj and current_user.role == "admin":
        return (
            jsonify({"app": app_obj.to_dict()}),
            200,
            {"Content-Type": "application/json"},
        )
    elif app_obj and current_user.role == "user":
        return (
            jsonify({"app": app_obj.to_limited_dict()}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "App not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/apps/check_title", methods=["POST"])
@jwt_required()
def check_app_title() -> Tuple[Response, int, Dict[str, str]]:
    """
    Checks if app title is unique.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    if request.json:
        app_title = request.json.get("title")

        if app_title:
            if App.query.filter_by(title=app_title).first() is not None:
                return (
                    jsonify({"error": "An app with this title already exists."}),
                    400,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"message": "App title is available."}),
                    200,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "No title provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/apps/check_unique_tag", methods=["POST"])
@jwt_required()
def check_app_unique_tag() -> Tuple[Response, int, Dict[str, str]]:
    """
    Checks if app unique tag is unique.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    if request.json:
        app_unique_tag = request.json.get("unique_tag")

        if app_unique_tag:
            if App.query.filter_by(unique_tag=app_unique_tag).first() is not None:
                return (
                    jsonify({"error": "An app with this unique tag already exists."}),
                    400,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"message": "App unique tag is available."}),
                    200,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "No unique tag provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/apps/check_url", methods=["POST"])
@jwt_required()
def check_app_url() -> Tuple[Response, int, Dict[str, str]]:
    """
    Checks if app url is unique.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    if request.json:
        app_url = request.json.get("url")

        if app_url:
            if App.query.filter_by(url=app_url).first() is not None:
                return (
                    jsonify({"error": "An app with this url already exists."}),
                    400,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"message": "App url is available."}),
                    200,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "No url provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/apps/add", methods=["POST"])
@jwt_required()
def add_app() -> Tuple[Response, int, Dict[str, str]]:
    """
    Adds new app to database with data from request json.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to add apps."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        app_title = request.json.get("title")
        app_url = request.json.get("url")
        app_image = request.json.get("image")
        image_folder = request.json.get("image_folder")
        app_operating_system = request.json.get("operating_system")
        app_tags = request.json.get("tags", [])
        app_description = request.json.get("description")
        app_status = request.json.get("status")
        install_price = request.json.get("install_price")
        conversion_price = request.json.get("conversion_price")

        app_parameters = [
            app_title,
            app_url,
            app_operating_system,
            app_status,
        ]

        if all(app_parameters):
            if App.query.filter_by(title=app_title).first() is not None:
                return (
                    jsonify({"error": "An app with this title already exists."}),
                    409,
                    {"Content-Type": "application/json"},
                )

            tags_list = []
            for tag in app_tags:
                tag_obj = AppTag.query.filter_by(tag=tag).first()
                if tag_obj:
                    tags_list.append(tag_obj)
                else:
                    new_tag = AppTag(tag=tag)
                    db.session.add(new_tag)
                    db.session.commit()
                    tags_list.append(new_tag)

            new_app = App(
                title=app_title,
                url=app_url,
                operating_system=app_operating_system.lower(),
                tags=tags_list,
                description=app_description,
                status=app_status,
                install_price=install_price or 0.00,
                conversion_price=conversion_price or 0.00,
                image=f"{image_folder}/{app_image}"
                if app_image and image_folder
                else None,
            )
            db.session.add(new_app)
            db.session.commit()

            keitaro_id = KeitaroApi().add_stream_to_campaign(new_app.title, new_app.id)
            new_app.keitaro_id = keitaro_id
            db.session.commit()

            if app_operating_system.lower() == "android":
                new_app.allow_for_users()

            return (
                jsonify({"message": "App added successfully."}),
                200,
                {"Content-Type": "application/json"},
            )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/apps/update_status", methods=["PATCH"])
@jwt_required()
def update_app_status() -> Tuple[Response, int, Dict[str, str]]:
    """
    Updates app status in database with data from request json.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to update app status."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        app_id = request.json.get("id")
        app_status = request.json.get("status")

        app_parameters = [app_id, app_status]

        if all(app_parameters):
            app_obj = App.query.get(app_id)
            if app_obj:
                app_obj.status = app_status
                db.session.commit()
                return (
                    jsonify({"message": "App status updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "App not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/apps/delete", methods=["DELETE"])
@jwt_required()
def delete_app() -> Tuple[Response, int, Dict[str, str]]:
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to delete apps."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        app_id = request.json.get("id")
        deleted = request.json.get("deleted")

        if app_id is None or deleted is None:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )

        app_obj = App.query.get(app_id)
        if app_obj:
            if deleted:
                if app_obj.keitaro_id:
                    KeitaroApi().set_stream_deleted(app_obj.keitaro_id)
                app_obj.set_deleted(deleted)

                return (
                    jsonify({"success": True, "message": "App deleted successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"success": True, "message": "App not deleted."}),
                    200,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "App not found."}),
                404,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/apps/tags", methods=["GET"])
@jwt_required()
@check_user_status()
def app_tags() -> Tuple[Response, int, Dict[str, str]]:
    """
    Returns all app tags in API format.
    """
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)

    app_tags_query_all = AppTag.query.all()
    if app_tags_query_all and isinstance(app_tags_query_all, list):
        total_count = len(app_tags_query_all)
    elif app_tags_query_all and isinstance(app_tags_query_all, Query):
        total_count = app_tags_query_all.count()
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"app_tags": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    app_tags_query = AppTag.query.order_by(AppTag.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return (
        jsonify(
            {
                "app_tags": [tag.to_dict() for tag in app_tags_query],
                "total_count": total_count,
            }
        ),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/apps/tags/add", methods=["POST"])
@jwt_required()
def add_app_tag() -> Tuple[Response, int, Dict[str, str]]:
    """
    Adds new app tag to database with data from request json.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to add app tags."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        tag = request.json.get("tag")

        if tag:
            if AppTag.query.filter_by(tag=tag).first() is not None:
                return (
                    jsonify({"error": "An app tag with this name already exists."}),
                    409,
                    {"Content-Type": "application/json"},
                )

            new_tag = AppTag(tag=tag)
            db.session.add(new_tag)
            db.session.commit()

            return (
                jsonify({"message": "App tag added successfully."}),
                200,
                {"Content-Type": "application/json"},
            )
        else:
            return (
                jsonify({"error": "No tag provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/apps/allow_for_users", methods=["PATCH"])
@jwt_required()
def allow_app_for_users() -> Tuple[Response, int, Dict[str, str]]:
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to allow apps for users."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        app_id = request.json.get("id")
        allow_for_users = request.json.get("users")

        if app_id and allow_for_users:
            logging.info(f"app_id: {app_id}, allow_for_users: {allow_for_users}")
            app_obj = App.query.get(app_id)
            if app_obj:
                logging.info(f"app_obj: {app_obj}")
                app_obj.allow_for_users(allow_for_users)
                logging.info(f"app_obj.allowed_users: {app_obj.allowed_users}")

                return (
                    jsonify({"message": "App allowed for users successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "App not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/apps/disallow_for_users", methods=["PATCH"])
@jwt_required()
def disallow_app_for_users() -> Tuple[Response, int, Dict[str, str]]:
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to disallow apps for users."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        app_id = request.json.get("id")
        disallow_for_users = request.json.get("users")

        if app_id and disallow_for_users:
            app_obj = App.query.get(app_id)
            if app_obj:
                app_obj.disallow_for_users(disallow_for_users)

                return (
                    jsonify({"message": "App disallowed for users successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "App not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/campaigns", methods=["GET"])
@jwt_required()
@check_user_status()
def campaigns() -> Tuple[Response, int, Dict[str, str]]:
    """
    Returns all campaigns in API format.
    """
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)
    search_query = request.args.get("search_query")
    archived = request.args.get("archived")

    if not search_query and current_user.role == "admin":
        if archived is None:
            campaigns_query_all = Campaign.query.all()
        else:
            campaigns_query_all = Campaign.query.filter_by(archive=archived).all()
    elif not search_query and current_user.role == "user":
        if archived is None:
            campaigns_query_all = Campaign.query.filter_by(
                user_id=current_user.id
            ).all()
        else:
            campaigns_query_all = Campaign.query.filter_by(
                user_id=current_user.id, archive=archived
            ).all()
    elif search_query and current_user.role == "admin":
        # search all campaigns with title search_query
        if archived is None:
            campaigns_query_all = Campaign.query.filter(
                Campaign.title.ilike(f"%{search_query}%")
            ).all()
        else:
            campaigns_query_all = (
                Campaign.query.filter(Campaign.title.ilike(f"%{search_query}%"))
                .filter_by(archive=archived)
                .all()
            )
    elif search_query and current_user.role == "user":
        # search all campaigns with title search_query
        if archived is None:
            campaigns_query_all = (
                Campaign.query.filter(Campaign.title.ilike(f"%{search_query}%"))
                .filter_by(user_id=current_user.id)
                .all()
            )
        else:
            campaigns_query_all = (
                Campaign.query.filter(Campaign.title.ilike(f"%{search_query}%"))
                .filter_by(user_id=current_user.id, archive=archived)
                .all()
            )
    else:
        campaigns_query_all = []
    if campaigns_query_all and isinstance(campaigns_query_all, list):
        total_count = len(campaigns_query_all)
    elif campaigns_query_all and isinstance(campaigns_query_all, Query):
        total_count = campaigns_query_all.count()
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"campaigns": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    if not search_query and current_user.role == "admin":
        if archived is None:
            campaigns_query = Campaign.query.order_by(Campaign.id.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
        else:
            campaigns_query = (
                Campaign.query.filter_by(archive=archived)
                .order_by(Campaign.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )
    elif not search_query and current_user.role == "user":
        if archived is None:
            campaigns_query = (
                Campaign.query.filter_by(user_id=current_user.id)
                .order_by(Campaign.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )
        else:
            campaigns_query = (
                Campaign.query.filter_by(user_id=current_user.id, archive=archived)
                .order_by(Campaign.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )
    elif search_query and current_user.role == "admin":
        if archived is None:
            campaigns_query = (
                Campaign.query.filter(Campaign.title.ilike(f"%{search_query}%"))
                .order_by(Campaign.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )
        else:
            campaigns_query = (
                Campaign.query.filter(Campaign.title.ilike(f"%{search_query}%"))
                .filter_by(archive=archived)
                .order_by(Campaign.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )
    elif search_query and current_user.role == "user":
        if archived is None:
            campaigns_query = (
                Campaign.query.filter(Campaign.title.ilike(f"%{search_query}%"))
                .filter_by(user_id=current_user.id)
                .order_by(Campaign.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )
        else:
            campaigns_query = (
                Campaign.query.filter(Campaign.title.ilike(f"%{search_query}%"))
                .filter_by(user_id=current_user.id, archive=archived)
                .order_by(Campaign.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )
    else:
        campaigns_query = []

    if campaigns_query:
        campaigns = []
        for campaign_obj in campaigns_query:
            campaign_dict = campaign_obj.to_dict()
            campaigns.append(campaign_dict)
    else:
        campaigns = []

    return (
        jsonify({"campaigns": campaigns, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/campaigns/<int:campaign_id>", methods=["GET"])
@jwt_required()
@check_user_status()
def campaign_by_id(campaign_id: int) -> Tuple[Response, int, Dict[str, str]]:
    """
    Returns campaign by id in API format.

    Args:
        campaign_id (int): Campaign id.
    """
    if not current_user.role:
        return (
            jsonify({"error": "You are not allowed to this view."}),
            403,
            {"Content-Type": "application/json"},
        )

    campaign_obj = Campaign.query.get(campaign_id)
    if campaign_obj:
        if current_user.role != "admin" and campaign_obj.user_id != current_user.id:
            return (
                jsonify({"error": "You are not allowed to this view."}),
                403,
                {"Content-Type": "application/json"},
            )

        campaign_dict = campaign_obj.to_dict()
        campaign_dict["apps"] = [app.to_dict() for app in campaign_obj.apps]

        return (
            jsonify({"campaign": campaign_dict}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "Campaign not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/campaigns/add", methods=["POST"])
@jwt_required()
@check_user_status()
def add_campaign() -> Tuple[Response, int, Dict[str, str]]:
    """
    Adds new campaign to database with data from request json.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    if not current_user.role:
        return (
            jsonify({"error": "You are not allowed to add campaigns."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        operating_system = None
        apps = []
        apps_stats = []
        app_tags = []

        campaign_title = request.json.get("title")
        campaign_description = request.json.get("description")
        campaign_offer_url = request.json.get("offer_url")
        campaign_geo = request.json.get("geo")
        campaign_apps = request.json.get("apps")
        campaign_app_tags = request.json.get("tags")
        campaign_landing_id = request.json.get("landing_page")
        campaign_status = request.json.get("status")
        campaign_subuser_id = request.json.get("subuser_id")
        
        if not all([
            campaign_title,
            campaign_offer_url,
            campaign_geo,
            campaign_landing_id,
            campaign_status
        ]):
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )

        custom_parameters = request.json.get("custom_parameters")
        if custom_parameters:
            campaign_custom_parameters = custom_parameters
        else:
            campaign_custom_parameters = {}

        if campaign_apps:
            if sum([app_["weight"] for app_ in campaign_apps]) == 0:
                for app_ in campaign_apps:
                    app_["weight"] = 100 / len(campaign_apps)

            if sum([app_["weight"] for app_ in campaign_apps]) < 100:
                rest_weight = 100 - sum([app_["weight"] for app_ in campaign_apps])
            else:
                rest_weight = 0
            for app_ in campaign_apps:
                app_obj = App.query.get(app_["id"])
                if app_obj:
                    apps.append(app_["id"])
                    apps_stats.append(
                        {
                            "id": app_["id"],
                            "keitaro_id": app_obj.keitaro_id,
                            "weight": app_["weight"]
                            + rest_weight * app_["weight"] / 100,
                            "visits": 0,
                        }
                    )
                    if not operating_system:
                        operating_system = app_obj.operating_system
                    app_tags.extend([tag.tag for tag in app_obj.tags])
            if not operating_system:
                return (
                    jsonify(
                        {"error": "Can't find operating system for provided apps."}
                    ),
                    400,
                    {"Content-Type": "application/json"},
                )
        elif campaign_app_tags:
            app_tags = []
            for tag in campaign_app_tags:
                tag_obj = AppTag.query.filter_by(tag=tag).first()
                if tag_obj:
                    app_tags.append(tag_obj.tag)

                if operating_system is None:
                    for app_ in tag_obj.apps:
                        if app_.operating_system:
                            operating_system = app_.operating_system
                            break

        if not operating_system:
            return (
                jsonify(
                    {"error": "Can't find operating system for provided app tags."}
                ),
                400,
                {"Content-Type": "application/json"},
            )

        campaign_user_id = request.json.get("user")
        campaign_user = User.query.get(campaign_user_id)
        if campaign_user:
            campaign_user = campaign_user
        else:
            campaign_user_id = None
            campaign_user = None

        campaign_parameters = [campaign_title, campaign_user, campaign_geo]

        if all(campaign_parameters):
            landing = Landing.query.get(campaign_landing_id)
            if landing:
                campaign_landing_title = landing.title
            else:
                campaign_landing_title = "Unknown"
            subuser = (
                SubUser.query.get(campaign_subuser_id) if campaign_subuser_id else None
            )
            new_campaign = Campaign(
                title=campaign_title,
                offer_url=campaign_offer_url,
                geo=campaign_geo,
                apps=apps,
                apps_stats=apps_stats,
                app_tags=app_tags,
                operating_system=operating_system,
                user=campaign_user,
                user_id=campaign_user_id,
                subuser_id=subuser.id if subuser else None,
                description=campaign_description,
                landing_id=campaign_landing_id,
                landing_title=campaign_landing_title,
                custom_parameters=campaign_custom_parameters,
                status=campaign_status,
            )
            db.session.add(new_campaign)
            db.session.commit()
            return (
                jsonify({"message": "Campaign added successfully."}),
                200,
                {"Content-Type": "application/json"},
            )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/campaigns/update_status", methods=["PATCH"])
@jwt_required()
@check_user_status()
def update_campaign_status() -> Tuple[Response, int, Dict[str, str]]:
    """
    Updates campaign status in database with data from request json.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    if request.json:
        campaign_id = request.json.get("id")
        campaign_status = request.json.get("status")

        campaign_parameters = [campaign_id, campaign_status]

        if all(campaign_parameters):
            campaign_obj = Campaign.query.get(campaign_id)
            if campaign_obj:
                if (
                    current_user.role != "admin"
                    and campaign_obj.user_id != current_user.id
                ):
                    return (
                        jsonify(
                            {"error": "You are not allowed to update campaign status."}
                        ),
                        403,
                        {"Content-Type": "application/json"},
                    )

                campaign_obj.update_status(campaign_status)
                return (
                    jsonify({"message": "Campaign status updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Campaign not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/campaigns/send_to_archive", methods=["PATCH"])
@jwt_required()
@check_user_status()
def send_campaign_to_archive() -> Tuple[Response, int, Dict[str, str]]:
    """
    Sends campaign to archive.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    if request.json:
        campaign_id = request.json.get("id")
        is_archived = request.json.get("archived")

        if campaign_id and is_archived is not None:
            campaign_obj = Campaign.query.get(campaign_id)
            if campaign_obj:
                if (
                    current_user.role != "admin"
                    and campaign_obj.user_id != current_user.id
                ):
                    return (
                        jsonify(
                            {
                                "error": "You are not allowed to send campaign to archive."
                            }
                        ),
                        403,
                        {"Content-Type": "application/json"},
                    )

                campaign_obj.set_archived(is_archived)
                status = "archived" if is_archived else "restored from archive"
                return (
                    jsonify({"message": f"Campaign {status} successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Campaign not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/campaigns/update_subuser", methods=["PATCH"])
@jwt_required()
@check_user_status()
def update_campaign_subuser() -> Tuple[Response, int, Dict[str, str]]:
    if request.json:
        campaign_id = request.json.get("id")
        subuser_id = request.json.get("subuser_id")

        if subuser_id:
            subuser = SubUser.query.get(subuser_id)
            if subuser:
                subuser_id = subuser.id
            else:
                return (
                    jsonify({"error": "Subuser not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            subuser_id = None

        if campaign_id:
            campaign_obj = Campaign.query.get(campaign_id)
            if campaign_obj:
                if campaign_obj.user_id != current_user.id:
                    return (
                        jsonify(
                            {
                                "error": "You are not allowed to update this campaign subuser."
                            }
                        ),
                        403,
                        {"Content-Type": "application/json"},
                    )

                campaign_obj.update_subuser(subuser_id)
                if subuser_id:
                    action = "assigned"
                else:
                    action = "unassigned"

                return (
                    jsonify({"message": f"Subuser {action} successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Campaign not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Campaign id not provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/campaigns/update_info", methods=["PATCH"])
@jwt_required()
def update_campaign() -> Tuple[Response, int, Dict[str, str]]:
    return (
        jsonify({"error": "This endpoint is deprecated."}),
        400,
        {"Content-Type": "application/json"},
    )

    if request.json:
        campaign_id = request.json.get("id")
        if campaign_id:
            campaign_obj = Campaign.query.get(campaign_id)
            if campaign_obj:
                campaign_info = request.json.copy().pop("id")
                campaign_obj.update_info(**campaign_info)
                return (
                    jsonify({"message": "Campaign info updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Campaign not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "No campaign id provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/campaigns/<int:campaign_id>/stats", methods=["GET"])
@jwt_required()
@check_user_status()
def campaign_statistics(campaign_id: int) -> Tuple[Response, int, Dict[str, str]]:
    """
    Returns campaign statistics by id in API format.

    Args:
        campaign_id (int): Campaign id.
    """
    campaign_obj = Campaign.query.get(campaign_id)
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)
    search_query = request.args.get("search_query")

    if campaign_obj:
        if current_user.role != "admin" and campaign_obj.user_id != current_user.id:
            return (
                jsonify(
                    {"success": False, "error": "You are not allowed to this view."}
                ),
                403,
                {"Content-Type": "application/json"},
            )

        clicks = 0
        installs = 0
        registrations = 0
        deposits = 0
        if not search_query:
            campaign_logs = LogMessage.query.filter_by(campaign=campaign_obj).all()

            if campaign_logs:
                for log in campaign_logs:
                    if log.event == "click":
                        clicks += 1
                    elif log.event == "install":
                        installs += 1
                    elif log.event == "registration":
                        registrations += 1
                    elif log.event == "deposit":
                        deposits += 1
            total_count = len(campaign_logs)
        else:
            campaign_logs = LogMessage.query.filter_by(
                campaign=campaign_obj, event=search_query
            ).all()
            for log in campaign_logs:
                if log.event == "click":
                    clicks += 1
                elif log.event == "install":
                    installs += 1
                elif log.event == "registration":
                    registrations += 1
                elif log.event == "deposit":
                    deposits += 1
            total_count = len(campaign_logs)

        if total_count == 0:
            return (
                jsonify(
                    {
                        "success": True,
                        "logs": [],
                        "total_count": 0,
                        "stats": {
                            "clicks": clicks,
                            "installs": installs,
                            "registrations": registrations,
                            "deposits": deposits,
                        },
                    }
                ),
                200,
                {"Content-Type": "application/json"},
            )

        if not search_query:
            campaign_logs_query = (
                LogMessage.query.filter_by(campaign=campaign_obj)
                .order_by(LogMessage.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )

            return (
                jsonify(
                    {
                        "success": True,
                        "logs": [log.to_dict() for log in campaign_logs_query],
                        "total_count": total_count,
                        "stats": {
                            "clicks": clicks,
                            "installs": installs,
                            "registrations": registrations,
                            "deposits": deposits,
                        },
                    }
                ),
                200,
                {"Content-Type": "application/json"},
            )
        else:
            campaign_logs_query = (
                LogMessage.query.filter_by(campaign=campaign_obj, event=search_query)
                .order_by(LogMessage.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )

            return (
                jsonify(
                    {
                        "logs": [log.to_dict() for log in campaign_logs_query],
                        "total_count": total_count,
                        "clicks": clicks,
                        "installs": installs,
                        "registrations": registrations,
                        "deposits": deposits,
                    }
                ),
                200,
                {"Content-Type": "application/json"},
            )

    else:
        return (
            jsonify({"error": "Campaign not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/campaigns/delete/<int:campaign_id>", methods=["DELETE"])
@jwt_required()
@check_user_status()
def delete_campaign(campaign_id: int) -> Tuple[Response, int, Dict[str, str]]:
    """
    Deletes campaign from database by id.

    Args:
        campaign_id (int): Campaign id.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    campaign_obj = Campaign.query.get(campaign_id)
    if campaign_obj:
        if current_user.role != "admin" and campaign_obj.user_id != current_user.id:
            return (
                jsonify({"error": "You are not allowed to delete this campaign."}),
                403,
                {"Content-Type": "application/json"},
            )

        db.session.delete(campaign_obj)
        db.session.commit()
        return (
            jsonify({"message": "Campaign deleted successfully."}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "Campaign not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/google_conversions", methods=["GET"])
@jwt_required()
def google_conversions() -> Tuple[Response, int, Dict[str, str]]:
    """
    Returns all google conversions in API format.
    """
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)

    if current_user.role == "admin":
        conversions_query_all = GoogleConversion.query.all()
    else:
        conversions_query_all = GoogleConversion.query.filter_by(
            user_id=current_user.id
        ).all()
        
    if conversions_query_all and isinstance(conversions_query_all, list):
        total_count = len(conversions_query_all)
    elif conversions_query_all and isinstance(conversions_query_all, Query):
        total_count = conversions_query_all.count()
    else:
        total_count = 0
        
    if total_count == 0:
        return (
            jsonify({
                "success": True,
                "google_conversions": [], 
                "total_count": 0
                }),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        if current_user.role == "admin":
            conversions_query = GoogleConversion.query.order_by(
                GoogleConversion.id.desc()
            ).paginate(page=page, per_page=per_page, error_out=False)
        else:
            conversions_query = (
                GoogleConversion.query.filter_by(user_id=current_user.id)
                .order_by(GoogleConversion.id.desc())
                .paginate(page=page, per_page=per_page, error_out=False)
            )

        return (
            jsonify(
                {
                    "success": True,
                    "google_conversions": [
                        conversion.to_dict() for conversion in conversions_query
                    ],
                    "total_count": total_count,
                }
            ),
            200,
            {"Content-Type": "application/json"},
        )
    

@api_endpoint.route("/google_conversions/add", methods=["POST"])
@jwt_required()
def add_google_conversion() -> Tuple[Response, int, Dict[str, str]]:
    """
    Adds new google conversion to database with data from request json.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    if not request.json:
        return (
            jsonify({
                "success": False,
                "error": "No json data."
                }),
            400,
            {"Content-Type": "application/json"},
        )
        
    name = request.json.get("name")
    gtag = request.json.get("gtag")
    install_clabel = request.json.get("install_clabel")
    reg_clabel = request.json.get("reg_clabel")
    dep_clabel = request.json.get("dep_clabel")
    hash_key = (
        f"{name}{gtag}{install_clabel}{reg_clabel}{dep_clabel}{datetime.datetime.now().timestamp}"
    )
    rma = sha256(hash_key.encode()).hexdigest()[:16]
    
    if not all([name, gtag, install_clabel, reg_clabel, dep_clabel]):
        return (
            jsonify({
                "success": False,
                "error": "Not all parameters are set."
                }),
            400,
            {"Content-Type": "application/json"},
        )
    
    try:
        new_conversion = GoogleConversion(
            name=name,
            rma=rma,
            gtag=gtag,
            install_clabel=install_clabel,
            reg_clabel=reg_clabel,
            dep_clabel=dep_clabel,
            user_id=current_user.id
        )
        db.session.add(new_conversion)
        db.session.commit()
        return (
            jsonify({
                "success": True,
                "message": "Google conversion added successfully.",
                "data": new_conversion.to_dict()
                }),
            200,
            {"Content-Type": "application/json"},
        )
    except Exception as e:
        return (
            jsonify({
                "success": False,
                "error": str(e)
                }),
            500,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/registrant/add", methods=["POST"])
@jwt_required()
def add_registrant():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to add registrant."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        first_name = request.json.get("first_name")
        last_name = request.json.get("last_name")
        address = request.json.get("address")
        city = request.json.get("city")
        state_province = request.json.get("state_province")
        postal_code = request.json.get("postal_code")
        country = request.json.get("country")
        phone = request.json.get("phone")
        email = request.json.get("email")
        required_parameters = [
            first_name,
            last_name,
            address,
            city,
            state_province,
            postal_code,
            country,
            phone,
            email,
        ]
        if all(required_parameters):
            registrant = Registrant(
                first_name=first_name,
                last_name=last_name,
                address=address,
                city=city,
                state_province=state_province,
                postal_code=postal_code,
                country=country,
                phone=phone,
                email=email,
            )
            db.session.add(registrant)
            db.session.commit()
            return (
                jsonify({"message": "Registrant added successfully."}),
                200,
                {"Content-Type": "application/json"},
            )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/registrant", methods=["GET"])
@jwt_required()
def registrant():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to view registrant."}),
            403,
            {"Content-Type": "application/json"},
        )

    registrant = Registrant.query.first()
    if registrant:
        return (
            jsonify({"registrant": registrant.to_dict()}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "Registrant not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/registrant/update", methods=["PATCH"])
@jwt_required()
def update_registrant():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to update registrant."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        registrant = Registrant.query.first()
        if registrant:
            registrant.update_info(**request.json)

            return (
                jsonify({"message": "Registrant updated successfully."}),
                200,
                {"Content-Type": "application/json"},
            )
        else:
            return (
                jsonify({"error": "Registrant not found."}),
                404,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/top", methods=["GET"])
@jwt_required()
def top_domains() -> Tuple[Response, int, Dict[str, str]]:
    if current_user.role != "admin":
        return (
            jsonify(
                {"success": False, "error": "You are not allowed to view top domains."}
            ),
            403,
            {"Content-Type": "application/json"},
        )

    domains = TopDomain.query.all()
    if domains:
        return (
            jsonify(
                {"success": True, "top_domains": [domain.name for domain in domains]}
            ),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"success": True, "top_domains": []}),
            200,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/top/add", methods=["POST"])
@jwt_required()
def add_top_domain() -> Tuple[Response, int, Dict[str, str]]:
    if current_user.role != "admin":
        return (
            jsonify(
                {"success": False, "error": "You are not allowed to add top domains."}
            ),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        top_domain_name = request.json.get("name")
        top_domain = TopDomain.query.filter_by(name=top_domain_name).first()
        if top_domain:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Top domain with this name already exists.",
                    }
                ),
                409,
                {"Content-Type": "application/json"},
            )
        else:
            new_top_domain = TopDomain(name=top_domain_name)
            db.session.add(new_top_domain)
            db.session.commit()
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Top domain added successfully.",
                        "top_domain": top_domain_name,
                    }
                ),
                200,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains", methods=["GET"])
@jwt_required()
@check_user_status()
def domains() -> Tuple[Response, int, Dict[str, str]]:
    """
    Returns all domains in API format.
    """
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)
    search_query = request.args.get("search_query")

    if not search_query and current_user.role == "admin":
        domains_query_all = Domain.query.all()
    elif not search_query and current_user.role == "user":
        domains_query_all = Domain.query.filter_by(user_id=current_user.id).all()
    elif search_query and current_user.role == "admin":
        # search all domains with title search_query
        domains_query_all = Domain.query.filter(
            Domain.domain.ilike(f"%{search_query}%")
        )
    elif search_query and current_user.role == "user":
        # search all domains with title search_query
        domains_query_all = Domain.query.filter(
            Domain.domain.ilike(f"%{search_query}%")
        ).filter_by(user_id=current_user.id)
    else:
        domains_query_all = []
    if domains_query_all and isinstance(domains_query_all, list):
        total_count = len(domains_query_all)
    elif domains_query_all and isinstance(domains_query_all, Query):
        total_count = domains_query_all.count()
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"domains": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    if not search_query and current_user.role == "admin":
        domains_query = Domain.query.order_by(Domain.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
    elif not search_query and current_user.role == "user":
        domains_query = (
            Domain.query.filter_by(user_id=current_user.id)
            .order_by(Domain.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    elif search_query and current_user.role == "admin":
        domains_query = (
            Domain.query.filter(Domain.domain.ilike(f"%{search_query}%"))
            .order_by(Domain.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    elif search_query and current_user.role == "user":
        domains_query = (
            Domain.query.filter(Domain.domain.ilike(f"%{search_query}%"))
            .filter_by(user_id=current_user.id)
            .order_by(Domain.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    else:
        domains_query = []

    if domains_query:
        domains = [domain.to_dict() for domain in domains_query]
    else:
        domains = []

    return (
        jsonify({"domains": domains, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/users/<int:user_id>/domains", methods=["GET"])
@jwt_required()
@check_user_status()
def user_domains(user_id: int) -> Tuple[Response, int, Dict[str, str]]:
    """
    Returns all domains in API format for user with id user_id.

    Args:
        user_id (int): User id.
    """
    if current_user.role != "admin" and current_user.id != user_id:
        return (
            jsonify({"error": "You are not allowed to this view."}),
            403,
            {"Content-Type": "application/json"},
        )

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)
    search_query = request.args.get("search_query")

    if not search_query:
        domains_query_all = Domain.query.filter_by(user_id=user_id).all()
    else:
        # search all domains with title search_query
        domains_query_all = (
            Domain.query.filter(Domain.domain.ilike(f"%{search_query}%"))
            .filter_by(user_id=user_id)
            .all()
        )
    if domains_query_all and isinstance(domains_query_all, list):
        total_count = len(domains_query_all)
    elif domains_query_all and isinstance(domains_query_all, Query):
        total_count = domains_query_all.count()
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"domains": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    if not search_query:
        domains_query = (
            Domain.query.filter_by(user_id=user_id)
            .order_by(Domain.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    else:
        domains_query = (
            Domain.query.filter(Domain.domain.ilike(f"%{search_query}%"))
            .filter_by(user_id=user_id)
            .order_by(Domain.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

    if domains_query:
        domains = [domain.to_dict() for domain in domains_query]
    else:
        domains = []

    return (
        jsonify({"domains": domains, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/domains/<int:domain_id>", methods=["GET"])
@jwt_required()
@check_user_status()
def domain_by_id(domain_id: int) -> Tuple[Response, int, Dict[str, str]]:
    """
    Returns domain by id in API format.

    Args:
        domain_id (int): Domain id.
    """
    domain_obj = Domain.query.get(domain_id)
    if domain_obj:
        if current_user.role != "admin" and domain_obj.user_id != current_user.id:
            return (
                jsonify({"error": "You are not allowed to this view."}),
                403,
                {"Content-Type": "application/json"},
            )

        return (
            jsonify({"domain": domain_obj.to_dict()}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "Domain not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/check_domains", methods=["POST"])
@jwt_required()
def check_domains() -> Tuple[Response, int, Dict[str, str]]:
    """
    Checks if domains are available.

    Returns:
        A tuple containing a JSON response with a message or error, a status code,
        and a dictionary with content type.
    """
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to check domains."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        domains = request.json.get("domains")

        if domains:
            namecheap_api = NamecheapApi(**namecheap_api_params)
            checked_domains = namecheap_api.check_domains_availability(domains)
            result = [
                {"domain": domain, "available": available}
                for domain, available in checked_domains.items()
            ]

            return (
                jsonify({"domains": result}),
                200,
                {"Content-Type": "application/json"},
            )
        else:
            return (
                jsonify({"error": "No domain provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/add", methods=["POST"])
@jwt_required()
def add_domains():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to add domains."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        domains = request.json.get("domains")
        test = request.json.get("test", False)
        user_id = request.json.get("user_id")
        if domains:
            if len(domains) > 50:
                return (
                    jsonify({"error": "You can add up to 50 domains at once."}),
                    400,
                    {"Content-Type": "application/json"},
                )

            result = []
            for domain in domains:
                result.append(add_domain(domain, test, user_id))

            return (
                jsonify({"domains": result}),
                200,
                {"Content-Type": "application/json"},
            )
        else:
            return (
                jsonify({"error": "No domains provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/get_info", methods=["POST"])
@jwt_required()
def get_domain_info():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to view domain info."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        domain = request.json.get("domain")
        if domain:
            namecheap_api = NamecheapApi(**namecheap_api_params)
            domain_info = namecheap_api.get_domain_info(domain)
            if domain_info:
                return (
                    jsonify({"domain": domain_info}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Domain not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "No domain provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/get_dns_hosts", methods=["POST"])
@jwt_required()
def get_domain_dns_hosts():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to view domain dns hosts."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        domain = request.json.get("domain")
        if domain:
            namecheap_api = NamecheapApi(**namecheap_api_params)
            dns_hosts = namecheap_api.get_domain_dns_hosts(domain)
            if dns_hosts:
                return (
                    jsonify({"dns_hosts": dns_hosts}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Domain not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "No domain provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/set_nameservers", methods=["POST"])
@jwt_required()
def get_ns_records():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to set nameservers."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        domain = request.json.get("domain")
        nameservers = request.json.get("nameservers")
        if domain and nameservers:
            namecheap_api = NamecheapApi(**namecheap_api_params)
            ns_set = namecheap_api.set_nameservers(domain, nameservers)
            if ns_set.get("success"):
                return (
                    jsonify({"message": "Nameservers set successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (jsonify(ns_set), 400, {"Content-Type": "application/json"})
        else:
            return (
                jsonify({"error": "No domain or nameservers provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/update_status", methods=["PATCH"])
@jwt_required()
def update_domain_status():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to update domain status."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        domain_id = request.json.get("id")
        domain_status = request.json.get("status")

        domain_parameters = [domain_id, domain_status]

        if all(domain_parameters):
            domain_obj = Domain.query.get(domain_id)
            if domain_obj:
                domain_obj.update_status(domain_status)
                db.session.commit()
                return (
                    jsonify({"message": "Domain status updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Domain not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/update_dns_hosts", methods=["POST"])
@jwt_required()
def update_hosts():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to update dns hosts."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        domain = request.json.get("domain")
        domain_obj = Domain.query.filter_by(domain=domain).first()
        if not domain_obj:
            return (
                jsonify({"error": "Domain not found."}),
                404,
                {"Content-Type": "application/json"},
            )

        if domain:
            domain_zone = get_domain_zone(domain)
            if domain_zone["success"]:
                for name in ["@", "www"]:
                    set_dns_records_on_cf(
                        domain_zone["zone_id"], current_app.config["DNS_HOST"], name
                    )
                return (
                    jsonify({"message": "DNS hosts updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (jsonify(domain_zone), 400, {"Content-Type": "application/json"})
        else:
            return (
                jsonify({"error": "No domain provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/assign_to_host", methods=["POST"])
@jwt_required()
def assign_domain_to_host():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to assign domain to host."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        domain_name = request.json.get("domain")
        if domain_name:
            domain_obj = Domain.query.filter_by(domain=domain_name).first()
            if not domain_obj:
                return (
                    jsonify({"error": "Domain not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )

            subdomains = [sub.subdomain for sub in domain_obj.subdomains]

            assigned = sc.add_domain_to_nginx(domain_name, subdomains)
            if assigned:
                return (
                    jsonify({"message": "Domain assigned successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Error assigning domain."}),
                    400,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "No domain provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/install_certificate", methods=["POST"])
@jwt_required()
def install_certificate():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to install certificate."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        domain = request.json.get("domain")
        if domain:
            domain_obj = Domain.query.filter_by(domain=domain).first()
            if not domain_obj:
                return (
                    jsonify({"error": "Domain not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )

            installed = sc.install_certbot_certificate(domain)
            if installed:
                return (
                    jsonify({"message": "Sertificate installed successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Error installing sertificate."}),
                    400,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "No domain provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/assign_to_user", methods=["PATCH"])
@jwt_required()
def assign_domain_to_user():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to assign domain to user."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        domain_id = request.json.get("id")
        user_id = request.json.get("user_id")

        domain_parameters = [domain_id, user_id]

        if all(domain_parameters):
            domain_obj = Domain.query.get(domain_id)
            user_obj = User.query.get(user_id)
            if domain_obj and user_obj:
                domain_obj.user_id = user_id
                new_transaction = Transaction(
                    user_id=user_id,
                    transaction_type="-",
                    amount=0.00,
                    reason="domain assigned by admin",
                )
                db.session.add(new_transaction)
                db.session.commit()

                return (
                    jsonify({"message": "Domain assigned successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            elif not domain_obj:
                return (
                    jsonify({"error": "Domain not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
            elif not user_obj:
                return (
                    jsonify({"error": "User not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Domain or user not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/update_subuser", methods=["PATCH"])
@jwt_required()
@check_user_status()
def update_subuser():
    if request.json:
        domain_id = request.json.get("id")
        subuser_id = request.json.get("subuser_id")
        subuser = SubUser.query.get(subuser_id) if subuser_id else None
        if not subuser:
            return (
                jsonify({"error": "Subuser not found."}),
                404,
                {"Content-Type": "application/json"},
            )

        else:
            domain_obj = Domain.query.get(domain_id)
            if not domain_obj:
                return (
                    jsonify({"error": "Domain not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )

            if domain_obj.user_id == current_user.id:
                domain_obj.subuser_id = subuser_id
                db.session.commit()
                return (
                    jsonify({"message": "Domain subuser updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Domain or user not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/domains/purchase", methods=["POST"])
@jwt_required()
@check_user_status()
def purchase_domain():
    if request.json:
        domain_id = request.json.get("id", None)
    else:
        domain_id = None

    # subdomains_count = request.json.get("subdomains_count", 0)
    if domain_id:
        domain_obj = Domain.query.get(domain_id)
    else:
        domain_obj = Domain.query.filter_by(user_id=None, status="active").first()

    if domain_obj and domain_obj.user_id:
        return (
            jsonify({"error": "This domain is already purchased."}),
            403,
            {"Content-Type": "application/json"},
        )

    if domain_obj and current_user.balance >= current_app.config["DOMAIN_PRICE"]:
        domain_obj.user_id = current_user.id
        current_user.subtract_balance(current_app.config["DOMAIN_PRICE"])
        new_transaction = Transaction(
            user_id=current_user.id,
            transaction_type="-",
            amount=float(current_app.config["DOMAIN_PRICE"]),
            reason="domain purchase",
        )
        db.session.add(new_transaction)
        db.session.commit()

        # purchased_subdomains = []
        # if subdomains_count > 0:
        #     for subdomain in domain_obj.subdomains:
        #         if subdomain.subdomain != "inapp":
        #             purchased_subdomains.append(subdomain.subdomain)
        #             subdomain.user_id = current_user.id
        #             subdomain.user = current_user
        #             subdomain.is_paid = True
        #         if len(purchased_subdomains) >= subdomains_count:
        #             break
        #     db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Domain purchased successfully.",
                    "domain": domain_obj.domain,
                    # "subdomains": purchased_subdomains,
                }
            ),
            200,
            {"Content-Type": "application/json"},
        )
    elif domain_obj and current_user.balance < current_app.config["DOMAIN_PRICE"]:
        return (
            jsonify({"error": "Not enough funds."}),
            400,
            {"Content-Type": "application/json"},
        )
    elif not domain_obj:
        return (
            jsonify({"error": "Domain not found."}),
            404,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "Domain or user not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/subdomains/check_subdomain", methods=["POST"])
@jwt_required()
def check_subdomain():
    if request.json:
        domain = request.json.get("domain")
        subdomain = request.json.get("subdomain")
        if domain and subdomain:
            search_subdomain = f"{subdomain}.{domain}"
            subdomain_obj = Subdomain.query.filter_by(
                subdomain=search_subdomain
            ).first()
            if subdomain_obj:
                return (
                    jsonify({"error": "Subdomain already exists."}),
                    400,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"message": "Subdomain is available."}),
                    200,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "No domain or subdomain provided."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


# @api_endpoint.route("/subdomains/add", methods=["POST"])
# @jwt_required()
# def add_subdomain():
#     if request.json:
#         domain = request.json.get("domain")
#         subdomain = request.json.get("subdomain")
#         user_id = request.json.get("user_id")
#         if domain and subdomain:
#             search_subdomain = f"{subdomain}.{domain}"
#             subdomain_obj = Subdomain.query.filter_by(
#                 subdomain=search_subdomain
#             ).first()
#             if subdomain_obj:
#                 return (
#                     jsonify({"error": "Subdomain already exists."}),
#                     400,
#                     {"Content-Type": "application/json"},
#                 )

#             domain_obj = Domain.query.filter_by(domain=domain).first()
#             if not domain_obj:
#                 return (
#                     jsonify({"error": "Domain not found."}),
#                     404,
#                     {"Content-Type": "application/json"},
#                 )

#             if current_user.role != "admin" and domain_obj.user_id != current_user.id:
#                 return (
#                     jsonify(
#                         {
#                             "error": "You are not allowed to add subdomains to this domain."
#                         }
#                     ),
#                     403,
#                     {"Content-Type": "application/json"},
#                 )

#             if len(domain_obj.subdomains) >= 10:
#                 return (
#                     jsonify(
#                         {"error": "You can add up to 10 subdomains to one domain."}
#                     ),
#                     400,
#                     {"Content-Type": "application/json"},
#                 )

#             subdomain_obj = Subdomain(
#                 subdomain=search_subdomain,
#                 status="active",
#                 expires=domain_obj.expires,
#                 domain_id=domain_obj.id,
#                 user_id=user_id,
#             )
#             db.session.add(subdomain_obj)
#             domain_obj.subdomains.append(subdomain_obj)
#             db.session.commit()

#             return (
#                 jsonify({"message": "Subdomain added successfully."}),
#                 200,
#                 {"Content-Type": "application/json"},
#             )

#         else:
#             return (
#                 jsonify({"error": "No domain or subdomain provided."}),
#                 400,
#                 {"Content-Type": "application/json"},
#             )
#     else:
#         return (
#             jsonify({"error": "No json data."}),
#             400,
#             {"Content-Type": "application/json"},
#         )


@api_endpoint.route("/domains/delete/<int:domain_id>", methods=["DELETE"])
@jwt_required()
def delete_domain(domain_id: int):
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to delete domains."}),
            403,
            {"Content-Type": "application/json"},
        )

    domain_obj = Domain.query.get(domain_id)
    if domain_obj:
        db.session.delete(domain_obj)
        db.session.commit()
        return (
            jsonify({"message": "Domain deleted successfully."}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "Domain not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/subdomains", methods=["GET"])
@jwt_required()
def subdomains():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)
    search_query = request.args.get("search_query")

    if not search_query and current_user.role == "admin":
        subdomains_query_all = Subdomain.query.all()
    elif not search_query and current_user.role == "user":
        subdomains_query_all = Subdomain.query.filter_by(user_id=current_user.id).all()
    elif search_query and current_user.role == "admin":
        # search all domains with title search_query
        subdomains_query_all = Subdomain.query.filter(
            Subdomain.subdomain.ilike(f"%{search_query}%")
        )
    elif search_query and current_user.role == "user":
        # search all domains with title search_query
        subdomains_query_all = Subdomain.query.filter(
            Subdomain.subdomain.ilike(f"%{search_query}%")
        ).filter_by(user_id=current_user.id)
    else:
        subdomains_query_all = []
    if subdomains_query_all and isinstance(subdomains_query_all, list):
        total_count = len(subdomains_query_all)
    elif subdomains_query_all and isinstance(subdomains_query_all, Query):
        total_count = subdomains_query_all.count()
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"subdomains": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    if not search_query and current_user.role == "admin":
        subdomains_query = Subdomain.query.order_by(Subdomain.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
    elif not search_query and current_user.role == "user":
        subdomains_query = (
            Subdomain.query.filter_by(user_id=current_user.id)
            .order_by(Subdomain.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    elif search_query and current_user.role == "admin":
        subdomains_query = (
            Subdomain.query.filter(Subdomain.subdomain.ilike(f"%{search_query}%"))
            .order_by(Subdomain.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    elif search_query and current_user.role == "user":
        subdomains_query = (
            Subdomain.query.filter(Subdomain.subdomain.ilike(f"%{search_query}%"))
            .filter_by(user_id=current_user.id)
            .order_by(Subdomain.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    else:
        subdomains_query = []

    if subdomains_query:
        subdomains = [subdomain.to_dict() for subdomain in subdomains_query]
    else:
        subdomains = []

    return (
        jsonify({"subdomains": subdomains, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/domains/<int:domain_id>/subdomains", methods=["GET"])
@jwt_required()
def domain_subdomains(domain_id):
    domain_obj = Domain.query.get(domain_id)
    if not domain_obj:
        return (
            jsonify({"error": "Domain not found."}),
            404,
            {"Content-Type": "application/json"},
        )

    if current_user.role != "admin" and domain_obj.user_id != current_user.id:
        return (
            jsonify({"error": "You are not allowed to view domain subdomains."}),
            403,
            {"Content-Type": "application/json"},
        )

    subdomains = Subdomain.query.filter_by(domain_id=domain_id).all()
    if subdomains:
        return (
            jsonify({"subdomains": [subdomain.to_dict() for subdomain in subdomains]}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (jsonify({"subdomains": []}), 200, {"Content-Type": "application/json"})


@api_endpoint.route("/users/<int:user_id>/subdomains", methods=["GET"])
@jwt_required()
def user_subdomains(user_id):
    if current_user.role != "admin" and current_user.id != user_id:
        return (
            jsonify({"error": "You are not allowed to view user subdomains."}),
            403,
            {"Content-Type": "application/json"},
        )

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)
    search_query = request.args.get("search_query")

    if not search_query:
        subdomains_query_all = Subdomain.query.filter_by(user_id=user_id).all()
    else:
        subdomains_query_all = (
            Subdomain.query.filter(Subdomain.subdomain.ilike(f"%{search_query}%"))
            .filter_by(user_id=user_id)
            .all()
        )
    if subdomains_query_all:
        total_count = len(subdomains_query_all)
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"subdomains": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    if not search_query:
        subdomains_query = (
            Subdomain.query.filter_by(user_id=user_id)
            .order_by(Subdomain.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    else:
        subdomains_query = (
            Subdomain.query.filter(Subdomain.subdomain.ilike(f"%{search_query}%"))
            .filter_by(user_id=user_id)
            .order_by(Subdomain.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

    if subdomains_query:
        subdomains = [subdomain.to_dict() for subdomain in subdomains_query]
    else:
        subdomains = []

    return (
        jsonify({"subdomains": subdomains, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/subdomains/<int:subdomain_id>", methods=["GET"])
@jwt_required()
def subdomain_by_id(subdomain_id):
    subdomain = Subdomain.query.get(subdomain_id)
    if subdomain:
        if current_user.role != "admin" and subdomain.user_id != current_user.id:
            return (
                jsonify({"error": "You are not allowed to this view."}),
                403,
                {"Content-Type": "application/json"},
            )

        return (
            jsonify({"subdomain": subdomain.to_dict()}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "Subdomain not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/subdomains/update_status", methods=["PATCH"])
@jwt_required()
def update_subdomain_status():
    if request.json:
        subdomain_id = request.json.get("id")
        subdomain_status = request.json.get("status")

        subdomain_parameters = [subdomain_id, subdomain_status]

        if all(subdomain_parameters):
            subdomain_obj = Subdomain.query.get(subdomain_id)
            if subdomain_obj:
                if (
                    current_user.role != "admin"
                    and subdomain_obj.user_id != current_user.id
                ):
                    return (
                        jsonify(
                            {"error": "You are not allowed to update subdomain status."}
                        ),
                        403,
                        {"Content-Type": "application/json"},
                    )

                subdomain_obj.update_status(subdomain_status)
                db.session.commit()
                return (
                    jsonify({"message": "Subdomain status updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Subdomain not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/subdomains/set_paid", methods=["PATCH"])
@jwt_required()
def set_subdomain_paid():
    if request.json:
        subdomain_id = request.json.get("id")
        subdomain_paid = request.json.get("paid")

        subdomain_parameters = [subdomain_id, subdomain_paid]

        if all(subdomain_parameters):
            subdomain_obj = Subdomain.query.get(subdomain_id)
            if subdomain_obj:
                if (
                    current_user.role != "admin"
                    and subdomain_obj.user_id != current_user.id
                ):
                    return (
                        jsonify(
                            {"error": "You are not allowed to update subdomain status."}
                        ),
                        403,
                        {"Content-Type": "application/json"},
                    )

                subdomain_obj.update_paid(subdomain_paid)
                db.session.commit()
                return (
                    jsonify({"message": "Subdomain status updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Subdomain not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )

    return (
        jsonify({"message": "Subdomain status updated successfully."}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/landings", methods=["GET"])
@jwt_required()
@check_user_status()
def landings():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)
    search_query = request.args.get("search_query")

    if not search_query:
        landings_query_all = Landing.query.all()
    else:
        landings_query_all = Landing.query.filter(
            Landing.title.ilike(f"%{search_query}%")
            | Landing.geo.ilike(f"%{search_query}%")
        ).all()
    if landings_query_all:
        total_count = len(landings_query_all)
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"landings": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    if not search_query:
        landings_query = Landing.query.order_by(Landing.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
    else:
        landings_query = (
            Landing.query.filter(
                Landing.title.ilike(f"%{search_query}%")
                | Landing.geo.ilike(f"%{search_query}%")
            )
            .order_by(Landing.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

    if landings_query:
        landings = [landing.to_dict() for landing in landings_query]
    else:
        landings = []

    return (
        jsonify({"landings": landings, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/landings/<int:landing_id>", methods=["GET"])
@jwt_required()
@check_user_status()
def landing_by_id(landing_id):
    landing = Landing.query.get(landing_id)
    if landing:
        return (
            jsonify({"landing": landing.to_dict()}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "Landing not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/landings/add", methods=["POST"])
@jwt_required()
def add_landing():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to add landings."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        landing_name = request.json.get("title")
        landing_description = request.json.get("description")
        landing_geo = request.json.get("geo")
        landing_working_directory = request.json.get("working_directory")
        landing_zip_file = request.json.get("zip_file")
        landing_status = request.json.get("status")
        landing_tags = request.json.get("tags")
        landing_parameters = [
            landing_name,
            landing_working_directory,
            landing_zip_file,
            landing_status,
        ]

        if all(landing_parameters):
            landing_obj = Landing(
                title=landing_name,
                description=landing_description,
                geo=landing_geo,
                working_directory=landing_working_directory,
                zip_file=landing_zip_file,
                status=landing_status,
                tags=landing_tags,
            )
            db.session.add(landing_obj)
            db.session.commit()
            return (
                jsonify({"message": "Landing added successfully."}),
                200,
                {"Content-Type": "application/json"},
            )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/landings/update_status", methods=["PATCH"])
@jwt_required()
def update_landing_status():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to update landing status."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        landing_id = request.json.get("id")
        landing_status = request.json.get("status")

        landing_parameters = [landing_id, landing_status]

        if all(landing_parameters):
            landing_obj = Landing.query.get(landing_id)
            if landing_obj:
                landing_obj.update_status(landing_status)
                db.session.commit()
                return (
                    jsonify({"message": "Landing status updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Landing not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/landings/update", methods=["PATCH"])
@jwt_required()
def update_landing():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to update landings."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        landing_id = request.json.get("id")
        landing_info = {}
        for key, value in request.json.items():
            if key != "id":
                landing_info[key] = value

        landing_parameters = [landing_id, landing_info]

        if all(landing_parameters):
            landing_obj = Landing.query.get(landing_id)
            if landing_obj:
                landing_obj.update_info(**landing_info)
                db.session.commit()
                return (
                    jsonify({"message": "Landing updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Landing not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


# @api_endpoint.route('/campaign_links', methods=['GET'])
# @jwt_required()
def campaign_links():
    campaign_links_query = CampaignLink.query.all()
    if campaign_links_query:
        campaign_links = [
            campaign_link.to_dict() for campaign_link in campaign_links_query
        ]
    else:
        campaign_links = []

    return (
        jsonify({"campaign_links": campaign_links}),
        200,
        {"Content-Type": "application/json"},
    )


# @api_endpoint.route('/campaign_links/<int:campaign_link_id>', methods=['GET'])
# @jwt_required()
def campaign_link_by_id(campaign_link_id):
    campaign_link = CampaignLink.query.get(campaign_link_id)
    if campaign_link:
        return (
            jsonify({"campaign_link": campaign_link.to_dict()}),
            200,
            {"Content-Type": "application/json"},
        )
    else:
        return (
            jsonify({"error": "Campaign link not found."}),
            404,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/generate_campaign_link", methods=["POST"])
@jwt_required()
@check_user_status()
def generate_campaign_link():
    if request.json:
        domain_id = request.json.get("domain_id")
        subdomain_id = request.json.get("subdomain_id")
        campaign_id = request.json.get("campaign_id")
        additional_parameters = request.json.get("additional_parameters", {})

        user_obj = None
        domain_obj = None
        subdomain_obj = None

        if domain_id:
            domain_obj = Domain.query.get(domain_id)
        elif subdomain_id:
            subdomain_obj = Subdomain.query.get(subdomain_id)

        campaign_obj = Campaign.query.get(campaign_id)

        if campaign_obj and campaign_obj.user_id:
            if current_user.role != "admin" and campaign_obj.user_id != current_user.id:
                return (
                    jsonify(
                        {"error": "You are not allowed to generate thiscampaign links."}
                    ),
                    403,
                    {"Content-Type": "application/json"},
                )
            user_obj = User.query.get(campaign_obj.user_id)
        if subdomain_id and not subdomain_obj:
            return (
                jsonify({"error": "Subdomain not found."}),
                404,
                {"Content-Type": "application/json"},
            )
        elif domain_id and not domain_obj:
            return (
                jsonify({"error": "Domain not found."}),
                404,
                {"Content-Type": "application/json"},
            )
        elif not domain_id and not subdomain_id:
            return (
                jsonify({"error": "No domain or subdomain provided."}),
                400,
                {"Content-Type": "application/json"},
            )
        elif not campaign_obj:
            return (
                jsonify({"error": "Campaign not found."}),
                404,
                {"Content-Type": "application/json"},
            )

        if campaign_id and (subdomain_id or domain_id):
            if domain_obj:
                if (
                    current_user.role != "admin"
                    and domain_obj.user_id != current_user.id
                ):
                    return (
                        jsonify(
                            {
                                "error": "You are not allowed to generate this campaign links."
                            }
                        ),
                        403,
                        {"Content-Type": "application/json"},
                    )

                if additional_parameters:
                    ready_link = f"https://{domain_obj.domain}/?uchsik={campaign_obj.hash_code}&{urlencode(additional_parameters)}"
                else:
                    ready_link = (
                        f"https://{domain_obj.domain}/?uchsik={campaign_obj.hash_code}"
                    )
            elif subdomain_obj:
                if (
                    current_user.role != "admin"
                    and subdomain_obj.user_id != current_user.id
                ):
                    return (
                        jsonify(
                            {
                                "error": "You are not allowed to generate this campaign links."
                            }
                        ),
                        403,
                        {"Content-Type": "application/json"},
                    )

                ready_link = f"https://{subdomain_obj.subdomain}/?uchsik={campaign_obj.hash_code}&{urlencode(additional_parameters)}"
            else:
                return (
                    jsonify({"error": "Domain or subdomain not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )

            campaign_link_obj = CampaignLink(
                ready_link=ready_link,
                additional_parameters=additional_parameters,
                domain_id=domain_id,
                domain=domain_obj,
                subdomain_id=subdomain_id,
                subdomain=subdomain_obj,
                campaign_id=campaign_id,
                campaign=campaign_obj,
                user_id=user_obj.id if user_obj else None,
                user=user_obj if user_obj else None,
            )
            db.session.add(campaign_link_obj)
            db.session.commit()

            return (
                jsonify(
                    {
                        "message": "Campaign link generated successfully.",
                        "ready_link": ready_link,
                    }
                ),
                200,
                {"Content-Type": "application/json"},
            )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


# @api_endpoint.route('/campaign_links/update_status', methods=['PATCH'])
# @jwt_required()
def update_campaign_link_status():
    if request.json:
        campaign_link_id = request.json.get("id")
        campaign_link_status = request.json.get("status")

        campaign_link_parameters = [campaign_link_id, campaign_link_status]

        if all(campaign_link_parameters):
            campaign_link_obj = CampaignLink.query.get(campaign_link_id)
            if campaign_link_obj:
                campaign_link_obj.update_status(campaign_link_status)
                db.session.commit()
                return (
                    jsonify({"message": "Campaign link status updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Campaign link not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )


@api_endpoint.route("/campaign_clicks", methods=["GET"])
@jwt_required()
@check_user_status()
def campaign_clicks():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)

    if current_user.role == "admin":
        campaign_clicks_query = CampaignClick.query.all()
    elif current_user.role == "user":
        campaign_clicks_query = CampaignClick.query.filter_by(
            user_id=current_user.id
        ).all()
    else:
        campaign_clicks_query = []
    if campaign_clicks_query:
        total_count = len(campaign_clicks_query)
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"campaign_clicks": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    if current_user.role == "admin":
        campaign_clicks_query = CampaignClick.query.order_by(
            CampaignClick.id.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
    elif current_user.role == "user":
        campaign_clicks_query = (
            CampaignClick.query.filter_by(user_id=current_user.id)
            .order_by(CampaignClick.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    else:
        campaign_clicks_query = []

    if campaign_clicks_query:
        campaign_clicks = [
            campaign_click.to_dict() for campaign_click in campaign_clicks_query
        ]
    else:
        campaign_clicks = []

    return (
        jsonify({"campaign_clicks": campaign_clicks, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/geo_prices", methods=["GET"])
@jwt_required()
def geo_prices():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to view geo prices."}),
            403,
            {"Content-Type": "application/json"},
        )

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)

    geo_prices_query = GeoPrice.query.all()
    if geo_prices_query:
        total_count = len(geo_prices_query)
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"geo_prices": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    geo_prices_query = GeoPrice.query.order_by(GeoPrice.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    if geo_prices_query:
        geo_prices = [geo_price.to_dict() for geo_price in geo_prices_query]
    else:
        geo_prices = []

    return (
        jsonify({"geo_prices": geo_prices, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )


@api_endpoint.route("/geo_prices/update", methods=["PATCH"])
@jwt_required()
def update_geo_prices():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to update geo prices."}),
            401,
            {"Content-Type": "application/json"},
        )

    if request.json:
        geo_price_id = request.json.get("id")
        geo_price_install = request.json.get("install_price")
        geo_prise_conversion = request.json.get("conversion_price")

        if not isinstance(geo_price_install, float) or not isinstance(
            geo_prise_conversion, float
        ):
            return (
                jsonify({"error": "Invalid prices. Should be float values."}),
                400,
                {"Content-Type": "application/json"},
            )

        geo_price_parameters = [geo_price_id, geo_price_install, geo_prise_conversion]

        if all(geo_price_parameters):
            geo_price_obj = GeoPrice.query.get(geo_price_id)
            if geo_price_obj:
                geo_price_obj.update_prices(geo_price_install, geo_prise_conversion)
                db.session.commit()
                return (
                    jsonify({"message": "Geo price updated successfully."}),
                    200,
                    {"Content-Type": "application/json"},
                )
            else:
                return (
                    jsonify({"error": "Geo price not found."}),
                    404,
                    {"Content-Type": "application/json"},
                )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )


@api_endpoint.route("/geo_prices/add", methods=["POST"])
@jwt_required()
def add_geo_price():
    if current_user.role != "admin":
        return (
            jsonify({"error": "You are not allowed to add geo prices."}),
            403,
            {"Content-Type": "application/json"},
        )

    if request.json:
        geo = request.json.get("geo")
        install_price = request.json.get("install_price")
        conversion_price = request.json.get("conversion_price")

        if not isinstance(install_price, float) or not isinstance(
            conversion_price, float
        ):
            return (
                jsonify({"error": "Invalid prices. Should be float values."}),
                400,
                {"Content-Type": "application/json"},
            )

        if GeoPrice.query.filter_by(geo=geo).first():
            return (
                jsonify({"error": "Geo price already exists."}),
                409,
                {"Content-Type": "application/json"},
            )

        geo_price_parameters = [geo, install_price, conversion_price]

        if all(geo_price_parameters):
            geo_price_obj = GeoPrice(
                geo=geo,
                install_price=install_price,
                conversion_price=conversion_price,
            )
            db.session.add(geo_price_obj)
            db.session.commit()
            return (
                jsonify({"message": "Geo price added successfully."}),
                200,
                {"Content-Type": "application/json"},
            )
        else:
            return (
                jsonify({"error": "Not all parameters are set."}),
                400,
                {"Content-Type": "application/json"},
            )
    else:
        return (
            jsonify({"error": "No json data."}),
            400,
            {"Content-Type": "application/json"},
        )


@api_endpoint.route("/log_messages", methods=["GET"])
@jwt_required()
@check_user_status()
def log_messages():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)

    log_messages_query = LogMessage.query.all()
    if log_messages_query:
        total_count = len(log_messages_query)
    else:
        total_count = 0

    if total_count == 0:
        return (
            jsonify({"log_messages": [], "total_count": 0}),
            200,
            {"Content-Type": "application/json"},
        )

    log_messages_query = LogMessage.query.order_by(LogMessage.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    if log_messages_query:
        log_messages = [log_message.to_dict() for log_message in log_messages_query]
    else:
        log_messages = []

    return (
        jsonify({"log_messages": log_messages, "total_count": total_count}),
        200,
        {"Content-Type": "application/json"},
    )
    

@api_endpoint.route("/statistics", methods=["GET"])
def get_statistics():
    users = {
        "total": User.query.count(),
        "active": User.query.filter_by(status="active").count(),
        "blocked": User.query.filter_by(status="banned").count(),
    }
    
    apps = {
        "total": App.query.count(),
        "active": App.query.filter_by(status="active").count(),
        "blocked": App.query.filter_by(status="blocked").count(),
        "views": App.query.with_entities(func.sum(App.views)).first()[0] or 0,
        "installs": App.query.with_entities(func.sum(App.installs)).first()[0] or 0,
        "registrations": App.query.with_entities(func.sum(App.registrations)).first()[0] or 0,
        "deposits": App.query.with_entities(func.sum(App.deposits)).first()[0] or 0,
    }
    
    campaigns = {
        "total": Campaign.query.count(),
        "active": Campaign.query.filter_by(status="active").count(),
        "archived": Campaign.query.filter_by(status="blocked").count(),
        "clicks": Campaign.query.with_entities(func.sum(Campaign.clicks)).first()[0] or 0, 
        "blocked_clicks": Campaign.query.with_entities(func.sum(Campaign.blocked_clicks)).first()[0] or 0,
        "app_redirected_clicks": Campaign.query.with_entities(func.sum(Campaign.app_redirected_clicks)).first()[0] or 0,
    }
    
    statistics = {
        "users": User.query.count(),
    }
    
    return (
        jsonify({
            "success": True,
            "statistics": statistics
        }),
        200,
        {"Content-Type": "application/json"},
    )


# Error handlers


@api_endpoint.errorhandler(400)
def bad_request(error):
    return (
        jsonify({"error": "Bad request."}),
        400,
        {"Content-Type": "application/json"},
    )


@api_endpoint.errorhandler(404)
def not_found(error):
    return (jsonify({"error": "Not found."}), 404, {"Content-Type": "application/json"})


@api_endpoint.errorhandler(405)
def method_not_allowed(error):
    return (
        jsonify({"error": "Method not allowed."}),
        405,
        {"Content-Type": "application/json"},
    )


@api_endpoint.errorhandler(500)
def internal_server_error(error):
    return (
        jsonify({"error": "Internal server error."}),
        500,
        {"Content-Type": "application/json"},
    )

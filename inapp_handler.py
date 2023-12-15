from flask import Blueprint, jsonify


inapp_bp = Blueprint("inapp", __name__, subdomain="inapp")


@inapp_bp.route("/", methods=["GET"], subdomain="inapp")
def handle_inapp():
    return jsonify({"success": True, "message": "Inapp handler is working."})

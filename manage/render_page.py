import os
import secrets
from typing import TYPE_CHECKING

from flask import abort, make_response, render_template


# TODO duplicated from app


if TYPE_CHECKING:
    from models import Landing


def render_page(landing_obj: "Landing"):
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


def gererate_secret_key_from_number(number):
    key_length = 60
    random_string = secrets.token_hex(key_length // 2)

    return random_string + str(number)


def emergency():
    return render_template("pages/emergency_page.html")
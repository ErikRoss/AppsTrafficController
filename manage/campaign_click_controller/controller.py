import logging
from typing import TYPE_CHECKING, Union
from urllib.parse import urlparse, urlencode, parse_qs, ParseResult

from flask import jsonify

from config import IN_APP_HOSTS
from logger import save_log_message
from models import CampaignClick, Campaign
from .click_app import ClickApp
from .click_web import ClickWeb
from .exceptions import BaseError, NoValidError


if TYPE_CHECKING:
    from manage.global_threads_storage import GlobalThreadsStorage
    from flask import Request, Response
    from .objects.event_app import EventApp
    from .objects.event_web import EventWeb


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


class CampaignClickController(ClickApp, ClickWeb):
    LOG_WEB = "Receiver"
    LOG_APP = "Inapp receiver"
    
    request: "Request"
    global_threads_storage: "GlobalThreadsStorage"

    def __init__(self, request: "Request", global_threads_storage: "GlobalThreadsStorage"):
        self.request = request
        self.global_threads_storage = global_threads_storage

    def handle_and_get_response(self):
        try:

            if not self.request:
                raise NoValidError("No request found.")

            self.log(self.LOG_WEB, f"Requested url: {self.request.url} from {self.request.headers.get('X-Forwarded-For', self.request.remote_addr)}")

            # click from app
            if self.request.host in IN_APP_HOSTS:
                return self.handle_app_click()

            # click from web
            else:
                return self.handle_web_click()

        except BaseError as exc: # handle expected errors
            logger_module = self.LOG_APP if (self.request.host in IN_APP_HOSTS) else self.LOG_WEB
            self.log(logger_module, str(exc), "error")
            return self.error_response(str(exc), exc.STATUS_CODE)

        except: # handle other errors
            return self.error_response("Unexpected Server Error", 500)

    @classmethod
    def make_offer_url(cls, event: Union["EventApp", "EventWeb"], campaign: Campaign, campaign_click: CampaignClick):

        # extend protocol if not provided
        if not (
                campaign.offer_url.startswith('http://') or
                campaign.offer_url.startswith('https://')
        ):
            campaign.offer_url = 'https://' + campaign.offer_url
        else:
            campaign.offer_url = campaign.offer_url

        # merge GET attrs
        parsed_url = urlparse(campaign.offer_url)
        query_params = parse_qs(parsed_url.query)

        # noinspection PyTypeChecker
        query_params.update(
            campaign_click.request_parameters | campaign.custom_parameters | {
                'clid': event.clid,
                'kclid': campaign_click.kclid
            }
        )

        # noinspection PyArgumentList
        return ParseResult(
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            urlencode(query_params, doseq=True),
            parsed_url.fragment
        ).geturl()

    @classmethod
    def error_response(cls, msg: str, status_code: int = 400) -> tuple["Response", int, dict]:
        return jsonify({"error": msg}), status_code, {"Content-Type": "application/json"}

    @classmethod
    def log(cls, module: str, msg: str, level: str = "info", **kwargs) -> None:
        save_log_message(module, msg, level, **kwargs)
        getattr(logger, level)(msg + (f' {kwargs}' if kwargs else ''))
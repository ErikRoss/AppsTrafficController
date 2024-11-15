from typing import TYPE_CHECKING

from config import FLOW_HOST

if TYPE_CHECKING:
    from flask import Request


class EventApp:
    clid: str
    appclid: str
    pay: str | None
    event: str
    key: str | None
    amount: float
    ip: str | None
    country: str | None
    city: str | None

    def __init__(self, request: "Request"):
        self.clid = request.args.get('clid')
        self.appclid = request.args.get('appclid')
        self.pay = request.args.get('pay')
        self.key = request.args.get('key')
        self.amount = float(request.args.get("amount", 0.0))
        self.user_agent = request.headers.get("User-Agent")
        self.ip = request.headers.get(
            "CF-Connecting-IP"
            ) or request.headers.get(
            "X-Forwarded-For"
        )
        self.country = request.headers.get("CF-Ipcountry")
        self.city = request.headers.get("CF-Ipcity")

        self.event = 'install' if (request.host and request.host == FLOW_HOST) else request.args.get('event')
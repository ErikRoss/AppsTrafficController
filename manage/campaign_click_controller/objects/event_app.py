from typing import TYPE_CHECKING

from config import FLOW_HOST

if TYPE_CHECKING:
    from flask import Request


class EventApp:
    clid: str
    appclid: str
    pay: str
    event: str
    key: str | None
    amount: float

    def __init__(self, request: "Request"):
        self.clid = request.args.get('clid')
        self.appclid = request.args.get('appclid')
        self.pay = request.args.get('pay')
        self.key = request.args.get('key', None)
        self.amount = float(request.args.get('key', 0.0))

        self.event = 'install' if (request.host and request.host == FLOW_HOST) else request.args.get('event')
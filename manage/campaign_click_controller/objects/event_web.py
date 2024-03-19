import random
import secrets
from hashlib import sha256
from typing import TYPE_CHECKING

from models import CampaignClick

if TYPE_CHECKING:
    from flask import Request


class EventWeb:
    uchsik: str
    fbclid: str
    fbclid_hash: str
    rma: str
    pay: int
    ulb: int
    domain: str

    def __init__(self, request: "Request"):
        self.uchsik = request.args.get('uchsik')
        self.fbclid = request.args.get('fbclid', 'Unknown')
        self.fbclid_hash = sha256(self.fbclid.encode()).hexdigest()
        self.rma = request.args.get('rma', 'Unknown')
        self.pay = int(request.args.get('pay', random.randint(120, 210)))
        self.ulb = random.randint(10000000, 99999999)
        self.domain = request.headers.get("Host")
        self._clid = None

    @property
    def clid(self) -> str:
        """ Auto-generate unique event Click ID """

        # TODO make this value unique at the database level
        #  and handle duplicate exception instead of checking here.

        if not self._clid:
            for attempt in range(100):
                self._clid = secrets.token_hex(5)
                if not CampaignClick.query.filter_by(click_id=self._clid).first():
                    break
            else:
                raise ValueError('Failed to create click ID. more than 100 click IDs in a row are occupied')

        return self._clid

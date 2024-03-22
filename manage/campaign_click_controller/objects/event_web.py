from curses.ascii import isdigit
import random
from re import U
import secrets
from hashlib import sha256
from typing import TYPE_CHECKING, Optional, Union

from models import CampaignClick

if TYPE_CHECKING:
    from flask import Request


class EventWeb:
    uchsik: str
    psa: Union[str, int, None]
    psa_type: Optional[str]
    fbclid: Optional[str]
    gclid: Optional[str]
    ttclid: Optional[str]
    fbclid_hash: Optional[str]
    rma: str
    pay: int
    ulb: int
    domain: str
    user_agent: str
    ip: str

    def __init__(self, request: "Request"):
        try:
            pay = int(request.args.get('pay', random.randint(120, 210)))
        except ValueError:
            pay = random.randint(120, 210)
        
        domain = request.headers.get("Host")
        if not domain.startswith('http'):
            domain = f'https://{domain}'
            
        psa = request.args.get('psa')
        if not psa:
            psa_type = None
        elif psa.isdigit():
            psa = int(psa)
            psa_type = 'app'
        else:
            psa_type = 'tag'
        
        self.uchsik = request.args.get('uchsik')
        self.psa = psa
        self.psa_type = psa_type
        self.fbclid = request.args.get('fbclid')
        self.fbclid_hash = sha256(self.fbclid.encode()).hexdigest() if self.fbclid else None
        self.gclid = request.args.get('gclid')
        self.ttclid = request.args.get('ttclid')
        self.rma = request.args.get('rma', 'Unknown')
        self.pay = pay
        self.ulb = random.randint(10000000, 99999999)
        self.domain = request.headers.get("Host")
        self.user_agent = request.headers.get("User-Agent")
        self.ip = request.headers.get(
            "CF-Connecting-IP"
            ) or request.headers.get(
            "X-Forwarded-For"
        )
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

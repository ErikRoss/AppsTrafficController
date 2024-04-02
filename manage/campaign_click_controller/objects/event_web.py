from datetime import datetime
import random
from hashlib import sha256
from typing import TYPE_CHECKING, Optional, Union

from pytz import timezone

# from models import CampaignClick

if TYPE_CHECKING:
    from flask import Request


class EventWeb:
    uchsik: Optional[str]
    psa: Union[str, int, None]
    psa_type: Optional[str]
    fbclid: Optional[str]
    gclid: Optional[str]
    ttclid: Optional[str]
    click_source: Optional[str]
    fbclid_hash: Optional[str]
    rma: str
    pay: int
    ulb: int
    clabel: Optional[str]
    gtag: Optional[str]
    domain: Optional[str]
    user_agent: Optional[str]
    ip: str
    user_timezone: str
    utc_offset: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    key: str

    def __init__(self, request: "Request"):
        ip = request.headers.get(
            "CF-Connecting-IP"
            ) or request.headers.get(
            "X-Forwarded-For"
        )
        domain = request.headers.get("Host")
        if domain and not domain.startswith('http'):
            domain = f'https://{domain}'
        user_timezone = request.headers.get("Cf-Timezone", "Europe/Kiev")
        tz = timezone(user_timezone)
        lt = datetime.now(tz)
        utc_offset = lt.utcoffset().total_seconds() / 3600
        latitude = request.headers.get("Cf-Iplatitude")
        longitude = request.headers.get("Cf-Iplongitude")

        try:
            pay = int(request.args.get('pay', random.randint(120, 210)))
        except ValueError:
            pay = random.randint(120, 210)
            
        psa = request.args.get('psa')
        if not psa:
            psa_type = None
        elif psa.isdigit():
            psa = int(psa)
            psa_type = 'app'
        else:
            psa_type = 'tag'
        
        self.psa = psa
        self.psa_type = psa_type
        
        self.user_timezone = user_timezone
        self.utc_offset = utc_offset
        self.latitude = float(latitude) if latitude else None
        self.longitude = float(longitude) if longitude else None
        self.ip = ip or "Unknown"
        self.user_agent = request.headers.get("User-Agent")
        self.domain = domain
        self.uchsik = request.args.get('uchsik')
        self.fbclid = request.args.get('fbclid')
        self.fbclid_hash = sha256(self.fbclid.encode()).hexdigest() if self.fbclid else None
        self.gclid = request.args.get('gclid')
        self.ttclid = request.args.get('ttclid')
        self.rma = request.args.get('rma', 'Unknown')
        self.pay = pay
        self.ulb = random.randint(10000000, 99999999)
        self.clabel = request.args.get('clabel')
        self.gtag = request.args.get('gtag')
        
        if self.fbclid:
            self.click_source = 'facebook'
        elif self.gclid:
            self.click_source = 'google'
        elif self.ttclid:
            self.click_source = 'tiktok'
        else:
            self.click_source = None
        
        self.clid = sha256(
            f"{self.ip}{self.ulb}{self.user_agent}{datetime.now().timestamp()}"
            .encode()
        ).hexdigest()[:10]

        if self.click_source == "facebook" and self.fbclid:
            self.key = sha256(self.fbclid.encode()).hexdigest()
        elif self.click_source == "google" and self.gclid:
            self.key = sha256(self.gclid.encode()).hexdigest()
        elif self.click_source == "tiktok" and self.ttclid:
            self.key = sha256(self.ttclid.encode()).hexdigest()
        else:
            self.key = sha256(f"{self.clid}".encode()).hexdigest()

    # @property
    # def clid(self) -> str:
    #     """ Auto-generate unique event Click ID """

    #     # TODO make this value unique at the database level
    #     #  and handle duplicate exception instead of checking here.

    #     self._clid = sha256(f"{self.ip}{self.ulb}{self.user_agent}".encode()).hexdigest()[:10]

    #     return self._clid

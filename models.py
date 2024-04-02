from datetime import datetime
from hashlib import sha256
import secrets
from typing import Optional

from flask_login import UserMixin
import pytz
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash

from config import SQLALCHEMY_DATABASE_URI as db_uri
from config import SERVICE_TAG as service_tag
from database import db


engine = create_engine(db_uri, echo=True)
db_session = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)
Base = declarative_base()
Base.query = db_session.query_property()

timezone = pytz.timezone('Europe/Kiev')


class User(db.Model, UserMixin):
    __tablename__ = "Users"

    id = db.Column(db.Integer, primary_key=True)
    hash_code = db.Column(db.String(64), unique=True)
    username = db.Column(db.String(50), unique=True)
    balance = db.Column(db.Float, default=0.00)
    email = db.Column(db.String(256), unique=True)
    telegram = db.Column(db.String(35))
    domains = relationship("Domain", backref="user")
    password_hash = db.Column(db.String(128))
    status = db.Column(db.String(20), default="active")
    role = db.Column(db.String(20), default="user")
    panel_key = db.Column(db.String(20), nullable=True)
    allowed_apps = relationship(
        "App", secondary="users_allowed_apps", back_populates="allowed_users"
    )

    def __init__(
        self,
        username: str,
        password: str,
        email: str,
        telegram: Optional[str] = None,
        role: str = "user",
    ):
        self.username = username
        self.password_hash = password
        self.email = email
        self.telegram = telegram
        self.role = role
        self.balance = round(0.00, 2)
        self.panel_key = secrets.token_hex(10)
        self.hash_code = self.generate_hash_code()

    def __repr__(self):
        return f"<User {self.username} ({self.email})>"

    def to_dict(self):
        if self.balance is None:
            self.balance = round(0.00, 2)
            db.session.commit()

        return {
            "id": self.id,
            "status": self.status,
            "role": self.role,
            "username": self.username,
            "balance": round(self.balance, 2),
            "email": self.email,
            "telegram": self.telegram,
            "domains": [domain.to_limited_dict() for domain in self.domains]
            if self.domains
            else [],
            "allowed_apps": [app.to_very_limited_dict() for app in self.allowed_apps],
        }

    def to_limited_dict(self):
        return {"id": self.id, "username": self.username}

    def update_status(self, status: str):
        self.status = status
        db.session.commit()

    def add_balance(self, amount: float) -> None:
        if self.balance is None:
            self.balance = 0.00
        self.balance += amount
        self.balance = round(self.balance, 2)
        db.session.commit()

    def subtract_balance(self, amount: float):
        if self.balance is None:
            self.balance = 0.00
        self.balance -= amount
        self.balance = round(self.balance, 2)
        db.session.commit()

    def update_password(self, password: str):
        self.password_hash = generate_password_hash(password)
        db.session.commit()

    def update_role(self, role: str):
        self.role = role
        db.session.commit()
    
    def generate_panel_key(self):
        """
        Generate 20 symbols key for panel
        """
        self.panel_key = secrets.token_hex(10)
        db.session.commit()
    
    def allow_apps(self, apps: list):
        """
        Allow apps for user
        """
        for app_ in apps:
            self.allowed_apps.append(app_)
        db.session.commit()
    
    def generate_hash_code(self):
        """
        Generate unique hash code for user
        """
        return sha256(f"user{self.username}{service_tag}{self.id}".encode()).hexdigest()[:12]
    
    def update_hash_code(self):
        """
        Update hash code for user
        """
        self.hash_code = self.generate_hash_code()
        db.session.commit()


class SubUser(db.Model):
    __tablename__ = "SubUsers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    color = db.Column(db.String(20))
    description = db.Column(db.String(255))
    owner_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    owner = relationship("User", backref="subusers")
    hash_code = db.Column(db.String(64), unique=True)

    def __init__(
        self,
        name: str,
        color: str,
        description: str,
        owner_id: int,
    ):
        self.name = name
        self.color = color
        self.description = description
        self.owner_id = owner_id
        self.hash_code = self.generate_hash_code()

    def __repr__(self):
        return f"<SubUser {self.name} ({self.owner.username})>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "description": self.description,
        }
    
    def generate_hash_code(self):
        """
        Generate unique hash code for subuser
        """
        return sha256(f"subuser{self.name}{service_tag}{self.id}".encode()).hexdigest()[:12]
    
    def update_hash_code(self):
        """
        Update hash code for subuser
        """
        self.hash_code = self.generate_hash_code()
        db.session.commit()


class Transaction(db.Model):
    __tablename__ = "Transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    user = relationship("User", backref="transactions")
    transaction_type = db.Column(db.String(20))
    amount = db.Column(db.Float)
    reason = db.Column(db.String(100))
    geo = db.Column(db.String(50), nullable=True)
    app_id = db.Column(db.Integer, db.ForeignKey("Apps.id"), nullable=True)
    os = db.Column(db.String(20), nullable=True)
    timestamp = db.Column(db.DateTime)

    def __init__(
        self,
        user_id: int,
        transaction_type: str,
        amount: float,
        reason: str,
        geo: Optional[str] = None,
        app_id: Optional[int] = None,
        os: Optional[str] = None,
    ):
        self.user_id = user_id
        self.transaction_type = transaction_type
        self.amount = amount
        self.reason = reason
        self.geo = geo
        self.timestamp = datetime.now(timezone)
        self.app_id = app_id
        self.os = os

    def __repr__(self):
        return (
            f"{self.user.username}|{self.transaction_type}|{self.amount}|{self.reason}"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "transaction_type": self.transaction_type,
            "amount": self.amount,
            "reason": self.reason,
            "geo": self.geo,
            "app_id": self.app_id,
            "os": self.os,
            "timestamp": self.timestamp,
        }


class App(db.Model):
    __tablename__ = "Apps"

    id = db.Column(db.Integer, primary_key=True)
    hash_code = db.Column(db.String(64), unique=True)
    created_at = db.Column(db.DateTime)
    keitaro_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(120), unique=True)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(300), nullable=True)
    image = db.Column(db.String(280), nullable=True)
    operating_system = db.Column(db.String(20))
    tags = relationship("AppTag", secondary="apps_tags", back_populates="apps")
    status = db.Column(db.String(20))
    is_deleted = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    installs = db.Column(db.Integer, default=0)
    registrations = db.Column(db.Integer, default=0)
    deposits = db.Column(db.Integer, default=0)
    install_price = db.Column(db.Float, default=0.00)
    conversion_price = db.Column(db.Float, default=0.00)

    campaigns = relationship(
        "Campaign", secondary="campaigns_apps", back_populates="apps"
    )
    allowed_users = relationship(
        "User", secondary="users_allowed_apps", back_populates="allowed_apps"
    )

    def __init__(
        self,
        title: str,
        description: str,
        url: str,
        operating_system: str,
        tags: list,
        status: str,
        image: Optional[str] = None,
        keitaro_id: Optional[int] = None,
        install_price: Optional[float] = 0.00,
        conversion_price: Optional[float] = 0.00,
    ):
        self.created_at = datetime.now(timezone)
        self.title = title
        self.url = url
        self.image = image
        self.operating_system = operating_system
        self.tags = tags
        self.description = description
        self.status = status
        self.keitaro_id = keitaro_id
        self.install_price = install_price
        self.conversion_price = conversion_price
        self.hash_code = self.generate_hash_code()

    def __repr__(self):
        return f"'{self.title}' (id: {self.id})"

    def to_dict(self):
        install_price = self.install_price or 0.00
        conversion_price = self.conversion_price or 0.00
        created_at = self.created_at or "Unknown"
        is_deleted = self.is_deleted or False
        
        return {
            "id": self.id,
            "hash_code": self.hash_code,
            "created_at": created_at,
            # "keitaro_id": self.keitaro_id,
            "title": self.title,
            "url": self.url,
            "image": self.image,
            "operating_system": self.operating_system,
            "tags": [tag.tag for tag in self.tags],
            "description": self.description,
            "status": self.status,
            "is_deleted": is_deleted,
            "views": self.views,
            "installs": self.installs,
            "registrations": self.registrations,
            "deposits": self.deposits,
            "install_price": install_price,
            "conversion_price": conversion_price,
            "allowed_users": [user.to_limited_dict() for user in self.allowed_users],
        }

    def to_limited_dict(self):
        return {
            "id": self.id,
            "hash_code": self.hash_code,
            "title": self.title,
            "image": self.image,
            "operating_system": self.operating_system,
            "tags": [tag.tag for tag in self.tags],
        }

    def to_very_limited_dict(self):
        return {
            "id": self.id,
            "title": self.title,
        }

    def update_status(self, status: str):
        self.status = status

    def allow_for_users(self, users: Optional[list] = None):
        if not users:
            users = User.query.all()
        else:
            users = User.query.filter(User.id.in_(users)).all()
        
        for user in users:
            if user and user not in self.allowed_users:
                self.allowed_users.append(user)
        db.session.commit()

    def disallow_for_users(self, users: list):
        for user in users:
            user_obj = User.query.get(user)
            if user_obj and user_obj in self.allowed_users:
                self.allowed_users.remove(user_obj)
        db.session.commit()

    def count_views(self):
        if self.views:
            self.views += 1
        else:
            self.views = 1

    def count_installs(self):
        if self.installs:
            self.installs += 1
        else:
            self.installs = 1

    def count_registrations(self):
        if self.registrations:
            self.registrations += 1
        else:
            self.registrations = 1

    def count_deposits(self):
        if self.deposits:
            self.deposits += 1
        else:
            self.deposits = 1
    
    def set_deleted(self, is_deleted: bool):
        self.is_deleted = is_deleted
        if is_deleted:
            self.status = "deleted"
        else:
            self.status = "inactive"
    
    def generate_hash_code(self):
        """
        Generate unique hash code for app
        """
        return sha256(f"app{self.title}{service_tag}{self.id}".encode()).hexdigest()[:12]
    
    def update_hash_code(self):
        self.hash_code = self.generate_hash_code()
        db.session.commit()


class AppTag(db.Model):
    __tablename__ = "AppsTags"

    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(25), unique=True)
    apps = relationship("App", secondary="apps_tags", back_populates="tags")

    def __init__(self, tag: str):
        self.tag = tag

    def __repr__(self):
        return f"<AppTag {self.tag}>"

    def to_dict(self):
        return {
            "id": self.id,
            "tag": self.tag,
            "apps": [app.id for app in self.apps] if self.apps else [],
        }

    def add_app(self, app: App):
        self.apps.append(app)
        db.session.commit()


class Campaign(db.Model):
    __tablename__ = "Campaigns"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120))
    description = db.Column(db.Text)
    offer_url = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=True)
    user = relationship("User", backref="campaigns")
    subuser_id = db.Column(db.Integer, db.ForeignKey("SubUsers.id"), nullable=True)
    subuser = relationship("SubUser", backref="campaigns")
    geo = db.Column(db.String(5))
    landing_title = db.Column(db.String(255), nullable=True)
    landing_id = db.Column(db.Integer, db.ForeignKey("Landings.id"), nullable=True)
    custom_parameters = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(255), nullable=True, default="inactive")
    archive = db.Column(db.Boolean, default=False)

    apps = relationship("App", secondary="campaigns_apps", back_populates="campaigns")
    apps_stats = db.Column(db.JSON, nullable=True)
    operating_system = db.Column(db.String(20))
    app_tags = db.Column(db.ARRAY(db.String(25)), nullable=True)

    hash_code = db.Column(db.String(64), unique=True)
    
    log_messages = relationship("LogMessage", back_populates="campaign")

    def __init__(
        self,
        title: str,
        offer_url: str,
        geo: str,
        apps: list,
        apps_stats: list,
        app_tags: list,
        operating_system: str,
        user: Optional[User] = None,
        user_id: Optional[int] = None,
        subuser_id: Optional[int] = None,
        description: str = "",
        landing_id: Optional[int] = None,
        landing_title: str = "",
        custom_parameters: dict = {},
        status: str = "inactive",
        hash_code: Optional[str] = None
    ):
        self.title = title
        self.offer_url = offer_url
        self.geo = geo
        self.landing_id = landing_id
        self.landing_title = landing_title
        self.description = description
        self.custom_parameters = custom_parameters
        self.user_id = user_id
        self.user = user
        self.subuser_id = subuser_id
        self.status = status

        for app_ in apps:
            self.apps.append(App.query.get(app_))
        self.apps_stats = apps_stats
        self.operating_system = operating_system
        self.app_tags = app_tags
        self.hash_code = hash_code or self.generate_hash_code()

    def generate_hash_code(self) -> str:
        return sha256(f"campaign{self.title}{service_tag}{self.id}".encode()).hexdigest()[:16]

    def __repr__(self):
        return f"<Campaign {self.id}>"

    def to_dict(self):
        apps_stats = []
        for app_ in self.apps_stats or []:
            try:
                app_.pop("keitaro_id")
            except KeyError:
                pass
            apps_stats.append(app_)
        
        subuser = SubUser.query.get(self.subuser_id) if self.subuser_id else None

        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "offer_url": self.offer_url,
            "user_id": self.user_id,
            "user_name": self.user.username if self.user else None,
            "subuser": subuser.to_dict() if subuser else None,
            "geo": self.geo,
            "apps": [app.id for app in self.apps],
            "apps_stats": apps_stats if self.apps_stats else [],
            "operating_system": self.operating_system,
            "tags": self.app_tags or [],
            "landing_id": self.landing_id,
            "landing_page": self.landing_title,
            "custom_parameters": self.custom_parameters,
            "hash_code": self.hash_code,
            "status": self.status,
            "archived": self.archive,
        }

    def update_status(self, status: str):
        self.status = status
        db.session.commit()

    def update_info(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        db.session.commit()

    def update_subuser(self, subuser_id: int):
        self.subuser_id = subuser_id
        db.session.commit()

    def set_archived(self, archived: bool):
        self.archive = archived
        db.session.commit()


class GoogleConversion(db.Model):
    __tablename__ = "GoogleConversions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    user = relationship("User", backref="google_conversations")
    rma = db.Column(db.String(255))
    gtag = db.Column(db.String(255))
    install_clabel = db.Column(db.String(255))
    reg_clabel = db.Column(db.String(255))
    dep_clabel = db.Column(db.String(255))
    
    def __init__(
        self,
        name: str,
        user_id: int,
        rma: str,
        gtag: str,
        install_clabel: str,
        reg_clabel: str,
        dep_clabel: str,
    ):
        self.name = name
        self.user_id = user_id
        self.rma = rma
        self.gtag = gtag
        self.install_clabel = install_clabel
        self.reg_clabel = reg_clabel
        self.dep_clabel = dep_clabel
    
    def __repr__(self):
        return f"<GoogleConversion {self.id}: {self.rma}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "user_id": self.user_id,
            "rma": self.rma,
            "gtag": self.gtag,
            "install_clabel": self.install_clabel,
            "reg_clabel": self.reg_clabel,
            "dep_clabel": self.dep_clabel,
        }


class TopDomain(db.Model):
    __tablename__ = "TopDomains"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    
    def __init__(self, name: str):
        self.name = name
        
    def __repr__(self):
        return f"<DomainZone {self.name}>"


class Domain(db.Model):
    __tablename__ = "Domains"

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(80))
    created = db.Column(db.DateTime, nullable=True)
    expires = db.Column(db.DateTime, nullable=True)
    redirected = db.Column(db.Boolean, nullable=True)
    proxied = db.Column(db.Boolean, nullable=True)
    https_rewriting = db.Column(db.Boolean, nullable=True, default=False)
    https_redirect = db.Column(db.Boolean, nullable=True, default=False)
    status = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=True)
    subuser_id = db.Column(db.Integer, db.ForeignKey("SubUsers.id"), nullable=True)
    subdomains = relationship("Subdomain", backref="domain", lazy=True)
    zone_id = db.Column(db.String(255), nullable=True)
    nameservers = db.Column(db.ARRAY(db.String(255)), nullable=True)

    def __init__(
        self,
        domain: str,
        created: datetime,
        expires: datetime,
        redirected: bool,
        proxied: bool,
        https_rewriting: bool,
        https_redirect: bool,
        status: str,
        user_id: Optional[int] = None,
    ):
        self.domain = domain
        self.created = created
        self.expires = expires
        self.redirected = redirected
        self.proxied = proxied
        self.https_rewriting = https_rewriting
        self.https_redirect = https_redirect
        self.status = status
        self.user_id = user_id

    def __repr__(self):
        return f"'{self.domain}'"

    def to_dict(self):
        subuser = SubUser.query.get(self.subuser_id) or None
        
        return {
            "id": self.id,
            "domain": self.domain,
            "created": self.created,
            "expires": self.expires,
            "redirected": self.redirected,
            "proxied": self.proxied,
            "https_rewriting": self.https_rewriting,
            "https_redirect": self.https_redirect,
            "status": self.status,
            "user_id": self.user_id,
            "subuser": subuser.to_dict() if subuser else None,
            # "subdomains": [subdomain.to_dict() for subdomain in self.subdomains]
            # if self.subdomains
            # else [],
        }

    def to_limited_dict(self):
        return {"id": self.id, "domain": self.domain}

    def update_status(self, status: str):
        self.status = status
        db.session.commit()

    def assing_to_user(self, user_id: int):
        self.user_id = user_id
        db.session.commit()

    def save(self):
        db.session.commit()


class Subdomain(db.Model):
    __tablename__ = "Subdomains"

    id = db.Column(db.Integer, primary_key=True)
    subdomain = db.Column(db.String(150))
    status = db.Column(db.String(20))
    expires = db.Column(db.DateTime, nullable=True)
    domain_id = db.Column(db.Integer, db.ForeignKey("Domains.id"))
    # domain = relationship('Domain', backref='subdomains', lazy=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=True)
    user = relationship("User", backref="subdomains", lazy=True)
    is_paid = db.Column(db.Boolean, default=False)

    def __init__(
        self,
        subdomain: str,
        status: str,
        expires: datetime,
        domain_id: int,
        user_id: Optional[int] = None,
        is_paid: bool = False,
    ):
        self.subdomain = subdomain
        self.status = status
        self.expires = expires
        self.domain_id = domain_id
        self.user_id = user_id
        self.is_paid = is_paid
        self.user = User.query.get(user_id) if user_id else None

    def __repr__(self):
        return f"<Subdomain {self.subdomain}>"

    def to_dict(self):
        return {
            "id": self.id,
            "subdomain": self.subdomain,
            "status": self.status,
            "expires": self.expires,
            "domain_id": self.domain_id,
            "user_id": self.user_id,
        }

    def update_status(self, status: str):
        self.status = status
        db.session.commit()

    def set_paid(self, status: bool):
        self.is_paid = status
        db.session.commit()


class Registrant(db.Model):
    __tablename__ = "Registrants"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    address = db.Column(db.String(100))
    city = db.Column(db.String(50))
    state_province = db.Column(db.String(50))
    postal_code = db.Column(db.String(10))
    country = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(50))

    def __init__(
        self,
        first_name: str,
        last_name: str,
        address: str,
        city: str,
        state_province: str,
        postal_code: str,
        country: str,
        phone: str,
        email: str,
    ):
        self.first_name = first_name
        self.last_name = last_name
        self.address = address
        self.city = city
        self.state_province = state_province
        self.postal_code = postal_code
        self.country = country
        self.phone = phone
        self.email = email

    def __repr__(self):
        return f"<Registrant {self.first_name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "address": self.address,
            "city": self.city,
            "state_province": self.state_province,
            "postal_code": self.postal_code,
            "country": self.country,
            "phone": self.phone,
            "email": self.email,
        }

    def update_info(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        db.session.commit()


class Landing(db.Model):
    __tablename__ = "Landings"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120))
    description = db.Column(db.Text, nullable=True)
    geo = db.Column(db.String(5), nullable=True)
    working_directory = db.Column(db.String(255))
    zip_file = db.Column(db.String(255))
    status = db.Column(db.String(20))
    tags = db.Column(db.ARRAY(db.String(25)), nullable=True)

    def __init__(
        self,
        title: str,
        description: str,
        geo: str,
        working_directory: str,
        zip_file: str,
        status: str,
        tags: list,
    ):
        self.title = title
        self.description = description
        self.geo = geo
        self.working_directory = working_directory
        self.zip_file = zip_file
        self.status = status
        self.tags = tags

    def __repr__(self):
        return f"<Landing {self.title} ({self.status})>"

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "geo": self.geo,
            "status": self.status,
            "tags": self.tags,
        }

    def update_status(self, status: str):
        self.status = status
        db.session.commit()

    def update_info(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        db.session.commit()


class CampaignLink(db.Model):
    __tablename__ = "CampaignsLinks"

    id = db.Column(db.Integer, primary_key=True)
    ready_link = db.Column(db.Text)
    additional_parameters = db.Column(db.JSON, nullable=True)
    comment = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default="active")
    domain_id = db.Column(db.Integer, db.ForeignKey("Domains.id"), nullable=True)
    domain = relationship("Domain", backref="links", lazy=True)
    subdomain_id = db.Column(db.Integer, db.ForeignKey("Subdomains.id"), nullable=True)
    subdomain = relationship("Subdomain", backref="links", lazy=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("Campaigns.id"))
    campaign = relationship("Campaign", backref="links")
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    user = relationship("User", backref="links")

    def __init__(
        self,
        ready_link: str,
        additional_parameters: dict,
        campaign_id: int,
        campaign: Campaign,
        domain_id: Optional[int] = None,
        domain: Optional[Domain] = None,
        subdomain_id: Optional[int] = None,
        subdomain: Optional[Subdomain] = None,
        comment: Optional[str] = None,
        user_id: Optional[int] = None,
        user: Optional[User] = None,
        status: str = "active",
    ):
        self.ready_link = ready_link
        self.additional_parameters = additional_parameters
        self.domain_id = domain_id
        self.domain = domain
        self.subdomain_id = subdomain_id
        self.subdomain = subdomain
        self.campaign_id = campaign_id
        self.campaign = campaign
        self.user_id = user_id
        self.user = user
        self.comment = comment
        self.status = status
        self.domain_id = domain_id
        self.domain = domain

    def __repr__(self):
        return f"<CampaignLink {self.id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "ready_link": self.ready_link,
            "additional_parameters": self.additional_parameters,
            "domain_id": self.domain_id,
            "domain": self.domain.domain if self.domain else None,
            "subdomain_id": self.subdomain_id,
            "subdomain": self.subdomain.subdomain if self.subdomain else None,
            "campaign_id": self.campaign_id,
            "campaign": self.campaign.title,
            "user_id": self.user_id,
            "user": self.user.username if self.user else None,
            "comment": self.comment,
        }

    def update_status(self, status: str):
        self.status = status
        db.session.commit()


class CampaignClick(db.Model):
    __tablename__ = "CampaignsClicks"

    id = db.Column(db.Integer, primary_key=True)
    log_messages = relationship("LogMessage", back_populates="click")
    click_id = db.Column(db.String(10))
    domain = db.Column(db.String(255))
    fbclid = db.Column(db.String(500))
    gclid = db.Column(db.String(500))
    ttclid = db.Column(db.String(500))
    click_source = db.Column(db.String(20))
    key = db.Column(db.String(100))
    rma = db.Column(db.String(255))
    ulb = db.Column(db.Integer)
    pay = db.Column(db.Integer, nullable=True, default=None)
    kclid = db.Column(db.String(255), nullable=True, default=None)
    clabel = db.Column(db.String(255), nullable=True, default=None)
    gtag = db.Column(db.String(255), nullable=True, default=None)
    request_parameters = db.Column(db.JSON)
    campaign_hash = db.Column(db.String(64))
    campaign_id = db.Column(db.Integer, db.ForeignKey("Campaigns.id"), nullable=True)
    campaign = relationship("Campaign", backref="clicks")
    app_id = db.Column(db.Integer, db.ForeignKey("Apps.id"), nullable=True)
    app = relationship("App", backref="clicks")
    app_installed = db.Column(db.Boolean, default=False)
    app_registered = db.Column(db.Boolean, default=False)
    app_deposited = db.Column(db.Boolean, default=False)
    appclid = db.Column(db.String(256), nullable=True, default=None)
    ip = db.Column(db.String(256))
    user_agent = db.Column(db.String(750))
    referer = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime)
    blocked = db.Column(db.Boolean, default=False)
    offer_url = db.Column(db.String(255), nullable=True)
    result = db.Column(db.String(120), nullable=True)
    conversion_event = db.Column(db.String(120), nullable=True)
    conversion_timestamp = db.Column(db.DateTime, nullable=True)
    conversion_sent = db.Column(db.Boolean, default=False)
    geo = db.Column(db.String(5), nullable=True)
    city = db.Column(db.String(50), nullable=True)
    device = db.Column(db.String(20), nullable=True)
    timezone = db.Column(db.String(50), nullable=True)
    utc_offset = db.Column(db.Float, nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    deposit_amount = db.Column(db.Float, nullable=True)
    hash_id = db.Column(db.String(6), nullable=True)

    def __init__(
        self,
        click_id: str,
        domain: Optional[str],
        rma: str,
        ulb: int,
        kclid: Optional[str],
        pay: Optional[int],
        request_parameters: dict,
        campaign_hash: Optional[str],
        campaign_id: int,
        campaign: Campaign,
        ip: str,
        user_agent: str,
        referer: str,
        timestamp: datetime,
        blocked: bool,
        fbclid: Optional[str] = None,
        gclid: Optional[str] = None,
        ttclid: Optional[str] = None,
        clabel: Optional[str] = None,
        gtag: Optional[str] = None,
        click_source: Optional[str] = None,
        key: Optional[str] = None,
        offer_url: Optional[str] = None,
        geo: Optional[str] = None,
        city: Optional[str] = None,
        device: Optional[str] = None,
        timezone: Optional[str] = None,
        utc_offset: Optional[float] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        hash_id: Optional[str] = None,
        app_id: Optional[int] = None,
    ):
        self.click_id = click_id
        self.domain = domain
        self.fbclid = fbclid
        self.gclid = gclid
        self.ttclid = ttclid
        self.click_source = click_source
        self.key = key
        self.rma = rma
        self.ulb = ulb
        self.kclid = kclid
        self.pay = pay
        self.clabel = clabel
        self.gtag = gtag
        self.request_parameters = request_parameters
        self.campaign_hash = campaign_hash
        self.campaign_id = campaign_id
        self.campaign = campaign
        self.offer_url = offer_url
        self.ip = ip
        self.user_agent = user_agent
        self.referer = referer
        self.timestamp = timestamp
        self.blocked = blocked
        self.geo = geo
        self.city = city
        self.device = device
        self.timezone = timezone
        self.utc_offset = utc_offset
        self.latitude = latitude
        self.longitude = longitude
        self.hash_id = hash_id
        self.app_id = app_id

    def __repr__(self):
        return f"<CampaignClick {self.id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "geo": self.geo,
            "city": self.city,
            "device": self.device,
            "click_id": self.click_id,
            "domain": self.domain,
            "fbclid": self.fbclid,
            "rma": self.rma,
            "ulb": self.ulb,
            "pay": self.pay,
            "clabel": self.clabel,
            "gtag": self.gtag,
            "request_parameters": self.request_parameters,
            "campaign_hash": self.campaign_hash,
            "campaign_id": self.campaign_id,
            "app_id": self.app_id,
            "app_installed": self.app_installed,
            "app_registered": self.app_registered,
            "app_deposited": self.app_deposited,
            "appclid": self.appclid,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "referer": self.referer,
            "timestamp": self.timestamp,
            "blocked": self.blocked,
            "offer_url": self.offer_url,
            "result": self.result,
            "conversion_event": self.conversion_event,
            "conversion_timestamp": self.conversion_timestamp,
            "conversion_sent": self.conversion_sent,
            "hash_id": self.hash_id,
        }

    def update_conversion(self, event: str, conversion_sent: bool = False):
        self.conversion_event = event
        self.conversion_sent = conversion_sent
        self.conversion_timestamp = datetime.now(timezone)
        db.session.commit()

    def install_app(self):
        self.app_installed = True


class GeoPrice(db.Model):
    __tablename__ = "GeoPrices"

    id = db.Column(db.Integer, primary_key=True)
    geo = db.Column(db.String(5))
    install_price = db.Column(db.Float, default=0.00)
    conversion_price = db.Column(db.Float, default=0.00)

    def __init__(
        self,
        geo: str,
        install_price: float,
        conversion_price: float,
    ):
        self.geo = geo
        self.install_price = install_price
        self.conversion_price = conversion_price

    def __repr__(self):
        return f"{self.geo}: {self.install_price}/{self.conversion_price}"

    def to_dict(self):
        return {
            "id": self.id,
            "geo": self.geo,
            "install_price": self.install_price,
            "conversion_price": self.conversion_price,
        }

    def update_prices(self, install_price: float, conversion_price: float):
        self.install_price = install_price
        self.conversion_price = conversion_price
        db.session.commit()


class LogMessage(db.Model):
    __tablename__ = "LogMessages"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("Campaigns.id"), nullable=True)
    campaign = relationship("Campaign")
    click_id = db.Column(db.Integer, db.ForeignKey("CampaignsClicks.id"), nullable=True)
    click = relationship("CampaignClick")
    event = db.Column(db.String(20))
    level = db.Column(db.String(10))
    module = db.Column(db.String(50))
    message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime)

    def __init__(
        self, 
        module: str, 
        message: str, 
        level: str, 
        click: Optional[CampaignClick] = None,
        campaign: Optional[Campaign] = None,
        event: Optional[str] = None,
    ):
        self.level = level
        self.module = module
        self.message = message
        self.timestamp = datetime.now(timezone)
        self.click = click
        self.campaign = campaign
        self.event = event

    def __repr__(self):
        return f"<LogMessage: {self.message}>"

    def to_dict(self):
        return {
            "id": self.id,
            "clid": self.click.click_id if self.click else None,
            "campaign_id": self.campaign.id if self.campaign else None,
            "event": self.event if self.event else None,
            "level": self.level,
            "module": self.module,
            "message": self.message,
            "timestamp": self.timestamp,
        }
    
    def to_stats_log(self):
        return {
            "id": self.id,
            "clid": self.click.click_id if self.click else None,
            "campaign_id": self.campaign.id if self.campaign else None,
            "event": self.event if self.event else None,
            "message": self.message,
            "timestamp": self.timestamp,
        }


campaigns_apps = db.Table(
    "campaigns_apps",
    db.Column(
        "campaign_id", 
        db.Integer, 
        db.ForeignKey("Campaigns.id"), 
        primary_key=True
        ),
    db.Column(
        "app_id", 
        db.Integer, 
        db.ForeignKey("Apps.id"), 
        primary_key=True
        ),
)

apps_tags = db.Table(
    "apps_tags",
    db.Column(
        "app_id", 
        db.Integer, 
        db.ForeignKey("Apps.id"), 
        primary_key=True
        ),
    db.Column(
        "tag_id", 
        db.Integer, 
        db.ForeignKey("AppsTags.id"), 
        primary_key=True
        ),
)

users_allowed_apps = db.Table(
    "users_allowed_apps",
    db.Column(
        "user_id", 
        db.Integer, 
        db.ForeignKey("Users.id"), 
        primary_key=True),
    db.Column(
        "app_id", 
        db.Integer, 
        db.ForeignKey("Apps.id"), 
        primary_key=True
        ),
)

# domains_users = db.Table(
#     'domains_users',
#     db.Column(
#         'domain_id',
#         db.Integer,
#         db.ForeignKey('Domains.id'),
#         primary_key=True
#         ),
#     db.Column(
#         'user_id',
#         db.Integer,
#         db.ForeignKey('Users.id'),
#         primary_key=True
#         )
#     )

# Create tables.
Base.metadata.create_all(bind=engine)

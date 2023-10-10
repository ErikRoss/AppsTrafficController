
import hashlib
import json

from flask_login import UserMixin
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base

from app import db, app

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], echo=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


class User(db.Model, UserMixin):
    __tablename__ = 'Users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(30))
    domains = relationship('Domain', secondary='domains_users', back_populates='users')

    def __init__(self, username: str, password: str, email: str):
        self.username = username
        self.password = password
        self.email = email

    def __repr__(self):
        return f'<User {self.username} ({self.email})>'


class App(db.Model):
    __tablename__ = 'Apps'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), unique=True)
    url = db.Column(db.String(500), unique=True)
    image = db.Column(db.String(500), nullable=True)
    operating_system = db.Column(db.String(120))
    tags = db.Column(db.String(255))
    unique_tag = db.Column(db.String(120), unique=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(120))
    
    campaigns = relationship('Campaign', secondary='campaigns_apps', back_populates='apps')

    def __init__(
        self,
        title: str,
        url: str,
        image: str,
        operating_system: str,
        tags: str,
        unique_tag: str,
        description: str,
        status: str
        ):
        self.title = title
        self.url = url
        self.image = image
        self.operating_system = operating_system
        self.tags = tags
        self.unique_tag = unique_tag
        self.description = description
        self.status = status
        
    def __repr__(self):
        return f'<App {self.title} ({self.url})>'
    
    def to_dict(self):
        return {
            'title': self.title,
            'url': self.url,
            'image': self.image,
            'operating_system': self.operating_system,
            'tags': self.tags,
            'unique_tag': self.unique_tag,
            'description': self.description,
            'status': self.status
            }


class Campaign(db.Model):
    __tablename__ = 'Campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    user = db.Column(db.Integer, db.ForeignKey('Users.id'))
    geo = db.Column(db.String(255))
    landing_page = db.Column(db.String(255), nullable=True)
    custom_parameters = db.Column(db.Text, nullable=True)
    
    apps = relationship('App', secondary='campaigns_apps', back_populates='campaigns')
    
    hash_code = db.Column(db.String(64))
    
    def __init__(
        self,
        title: str,
        user: int,
        geo: str,
        apps: list,
        description: str = '',
        landing_page: str = '',
        custom_parameters: str = ''
        ):
        self.title = title
        self.user = user
        self.geo = geo
        self.landing_page = landing_page
        self.description = description
        self.custom_parameters = custom_parameters
        
        for app in apps:
            self.apps.append(App.query.get(int(app)))
        
        self.hash_code = self.calculate_hash_sum()
    
    def calculate_hash_sum(self):
        hash_string = json.dumps({
            'title': self.title,
            'user': self.user,
            'geo': self.geo,
            'apps': [app.id for app in self.apps],
            'description': self.description,
            'custom_parameters': self.custom_parameters
            })
        self.hash_code = hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
        
        return self.hash_code
        
    def __repr__(self):
        return f'<Campaign {self.id}>'
    
    def to_dict(self):
        return {
            'title': self.title,
            'description': self.description,
            'user': self.user,
            'geo': self.geo,
            'apps': [app.id for app in self.apps],
            'landing_page': self.landing_page,
            'custom_parameters': self.custom_parameters,
            'hash_code': self.hash_code
            }
    
    
class Domain(db.Model):
    __tablename__ = 'Domains'
    
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255))
    status = db.Column(db.String(255))
    creating_date = db.Column(db.DateTime, nullable=True)
    users = relationship('User', secondary='domains_users', back_populates='domains')
    
    def __init__(self, domain: str, campaign: int, status: str, dns: str):
        self.domain = domain
        self.status = status
        self.creating_date = None
        
    def __repr__(self):
        return f'<Domain {self.id}>'
    
    def to_dict(self):
        return {
            'domain': self.domain,
            'status': self.status,
            'creating_date': self.creating_date,
            'users': [user.id for user in self.users]
            }

campaigns_apps = db.Table(
    'campaigns_apps',
    db.Column(
        'campaign_id', 
        db.Integer, 
        db.ForeignKey('Campaigns.id'), 
        primary_key=True
        ),
    db.Column(
        'app_id', 
        db.Integer, 
        db.ForeignKey('Apps.id'), 
        primary_key=True
        )
    )

domains_users = db.Table(
    'domains_users',
    db.Column(
        'domain_id', 
        db.Integer, 
        db.ForeignKey('Domains.id'), 
        primary_key=True
        ),
    db.Column(
        'user_id', 
        db.Integer, 
        db.ForeignKey('Users.id'), 
        primary_key=True
        )
    )

# Create tables.
Base.metadata.create_all(bind=engine)

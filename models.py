from flask_login import UserMixin
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
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

    def __init__(self, username: str = None, password: str = None, email: str = None):
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
    alias = db.Column(db.String(120), nullable=True)
    unique_tag = db.Column(db.String(120), unique=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(120))

    def __init__(self,
                 title: str,
                 url: str,
                 image: str,
                 operating_system: str,
                 alias: str,
                 unique_tag: str,
                 description: str,
                 status: str):
        self.title = title
        self.url = url
        self.image = image
        self.operating_system = operating_system
        self.alias = alias
        self.unique_tag = unique_tag
        self.description = description
        self.status = status


# Create tables.
Base.metadata.create_all(bind=engine)

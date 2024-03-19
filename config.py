import os

import pytz
from decouple import config

# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))
BASEDIR = os.path.abspath(os.path.dirname(__file__))

# Enable debug mode.
DEBUG = bool(config('DEBUG', cast=int))
# SERVER_NAME = "yoursapp.online"
# SERVER_NAME = "127.0.0.1:5000"

SECRET_KEY = config('DB_HOST')

# Connect to the database
DB_HOST = config('DB_HOST')
DB_NAME = config('DB_NAME')
DB_USER = config('DB_USER')
DB_PASSWORD = config('DB_PASSWORD')
DB_PORT = config('DB_PORT', cast=int)
SQLALCHEMY_DATABASE_URI = (
    "postgresql://{}:{}@{}:{}/{}".format(
        DB_USER,
        DB_PASSWORD,
        DB_HOST,
        DB_PORT,
        DB_NAME,
    )
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {'isolation_level': 'READ COMMITTED'} 

# Set folders for uploads
UPLOAD_FOLDER = "static/img/uploads"
LANDINGS_FOLDER = "templates/landings"

# Set DNS host IP for domain registration
DNS_HOST = "38.54.13.62"

# Set pameters for Namecheap API

# Developer account

# NAMECHEAP_CLIENT_IP = "188.163.96.228"
# NAMECHEAP_API_KEY = "d05fb607cffd4c5a836bb65aba9f3178"
# NAMECHEAP_USERNAME = "erikross"
# NAMECHEAP_SANDBOX = True

# Production account

NAMECHEAP_CLIENT_IP = config('NAMECHEAP_CLIENT_IP')
NAMECHEAP_API_KEY = config('NAMECHEAP_API_KEY')
NAMECHEAP_USERNAME = config('NAMECHEAP_USERNAME')
NAMECHEAP_SANDBOX = bool(config('NAMECHEAP_SANDBOX', cast=int))
NAMECHEAP_CONFIRM_EMAIL = config('NAMECHEAP_CONFIRM_EMAIL')

NAMECHEAP_API_SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"
NAMECHEAP_API_URL = "https://api.namecheap.com/xml.response"

# Set prices for domain, subdomain and conversion

DOMAIN_PRICE = 15
SUBDOMAIN_PRICE = 3
CONVERSION_INSTALL_PRICE_ANDROID = 0.06
CONVERSION_INSTALL_PRICE_IOS = 0.1
CONVERSION_REGISTRATION_PRICE_ANDROID = 0.0
CONVERSION_REGISTRATION_PRICE_IOS = 0.0
CONVERSION_DEPOSIT_PRICE_ANDROID = 0.0
CONVERSION_DEPOSIT_PRICE_IOS = 0.0


FLOW_HOST = config('FLOW_HOST')
EVENTS_HOST = config('EVENTS_HOST')
IN_APP_HOSTS = [FLOW_HOST, EVENTS_HOST]

TIME_ZONE = pytz.timezone(config('TIME_ZONE', default='UTC'))
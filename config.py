import os

# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))

# Enable debug mode.
DEBUG = True
# SERVER_NAME = "yoursapp.online"
# SERVER_NAME = "127.0.0.1:5000"

SECRET_KEY = "appmanager2023"

# Connect to the database
SQLALCHEMY_DATABASE_URI = (
    "postgresql://appscontroller:controller2023@localhost:5432/appscontroller"
)

# Set folders for uploads
UPLOAD_FOLDER = "static/img/uploads"
LANDINGS_FOLDER = "templates/landings"

# Set DNS host IP for domain registration
DNS_HOST = "38.54.122.209"

# Set pameters for Namecheap API

# Developer account

# NAMECHEAP_CLIENT_IP = "188.163.96.228"
# NAMECHEAP_API_KEY = "d05fb607cffd4c5a836bb65aba9f3178"
# NAMECHEAP_USERNAME = "erikross"
# NAMECHEAP_SANDBOX = True

# Production account

NAMECHEAP_CLIENT_IP = "38.54.122.209"
NAMECHEAP_API_KEY = "8eaea527895a44d69d1c9747ad555949"
NAMECHEAP_USERNAME = "nexodium"
NAMECHEAP_SANDBOX = False

NAMECHEAP_API_SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"
NAMECHEAP_API_URL = "https://api.namecheap.com/xml.response"

# Set prices for domain, subdomain and conversion

DOMAIN_PRICE = 15
SUBDOMAIN_PRICE = 3
CONVERSION_INSTALL_PRICE_ANDROID = 0.1
CONVERSION_INSTALL_PRICE_IOS = 0.1
CONVERSION_REGISTRATION_PRICE_ANDROID = 0.0
CONVERSION_REGISTRATION_PRICE_IOS = 0.0
CONVERSION_DEPOSIT_PRICE_ANDROID = 0.0
CONVERSION_DEPOSIT_PRICE_IOS = 0.0

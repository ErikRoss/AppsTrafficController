import os

# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))

# Enable debug mode.
DEBUG = True

# Secret key for session management. You can generate random strings here:
# https://randomkeygen.com/
SECRET_KEY = 'appmanager2023'

# Connect to the database
SQLALCHEMY_DATABASE_URI = 'postgresql://appscontroller:controller2023@localhost:5432/appscontroller'

# Set folder for uploads
UPLOAD_FOLDER = 'static/img/uploads'

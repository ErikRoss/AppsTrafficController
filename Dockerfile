FROM python:3.11-slim-bookworm

# set environment variables
ENV PYTHONUNBUFFERED 1

# set base directory
WORKDIR /app
ENV PYTHONPATH /app

# install ubuntu dependencies
RUN apt-get update
RUN apt-get -y install gcc libpq-dev

# upgrade pip version
RUN pip install --upgrade pip

# install requirements.txt
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# copy project files
COPY . .
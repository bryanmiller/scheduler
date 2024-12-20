FROM python:3.10-buster

ARG GH_PAT
# Default app version is development
ARG APP_VERSION="development"
# Set environment variables
ENV GH_PAT=$GH_PAT
ENV APP_VERSION=$APP_VERSION

WORKDIR /home

# Manage dependencies
COPY ./requirements.txt /home/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /home/requirements.txt

COPY ./scheduler /home/scheduler
COPY ./definitions.py /home/definitions.py

ENV PYTHONPATH "${PYTHONPATH}:/scheduler"
ENTRYPOINT [ "python", "/home/scheduler/main.py" ]

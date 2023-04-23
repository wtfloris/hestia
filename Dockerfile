# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster

WORKDIR /hestia

COPY requirements.txt requirements.txt

RUN apt-get update && apt-get install cron -y
RUN pip3 install -r requirements.txt

COPY hestia.py hestia.py
COPY scraper.py scraper.py
COPY secrets.py secrets.py
COPY targets.py targets.py

RUN echo "*/5 * * * * /usr/local/bin/python3 /hestia/scraper.py" >> /etc/crontab

CMD ["python3", "hestia.py"]


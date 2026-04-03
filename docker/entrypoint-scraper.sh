#!/bin/sh
DELAY=$(shuf -i 0-300 -n 1)
echo "*/5 * * * * root sleep $DELAY && /usr/local/bin/python3 /scraper/hestia/scraper.py > /proc/1/fd/1 2>/proc/1/fd/2" >> /etc/crontab
exec cron -f

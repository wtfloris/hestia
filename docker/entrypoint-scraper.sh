#!/bin/sh
DELAY=$(shuf -i 0-300 -n 1)
echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] agency=${HESTIA_TARGET:-maintenance} delay=${DELAY}s"
printenv | sed 's/=\(.*\)/="\1"/' > /etc/environment
echo "*/5 * * * * root . /etc/environment; sleep $DELAY && /usr/local/bin/python3 /scraper/hestia/scraper.py > /proc/1/fd/1 2>/proc/1/fd/2" >> /etc/crontab
exec cron -f

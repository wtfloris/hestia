#!/bin/sh
DELAY=$(shuf -i 0-300 -n 1)
SCHEDULE="${HESTIA_CRON_SCHEDULE:-*/5 * * * *}"
echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] agency=${HESTIA_TARGET:-maintenance} delay=${DELAY}s schedule='${SCHEDULE}'"
printenv | sed 's/=\(.*\)/="\1"/' > /etc/environment
# Overwrite a dedicated cron.d file (not >> /etc/crontab) so restarts, which re-run
# this entrypoint on the same writable layer, can't stack duplicate scrape entries.
echo "${SCHEDULE} root . /etc/environment; sleep $DELAY && /usr/local/bin/python3 /scraper/hestia/scraper.py > /proc/1/fd/1 2>/proc/1/fd/2" > /etc/cron.d/hestia
chmod 0644 /etc/cron.d/hestia
exec cron -f

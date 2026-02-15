import json
import logging
import requests
from time import sleep
from asyncio import run
from telegram.error import Forbidden
from datetime import datetime, timedelta

import hestia_utils.db as db
import hestia_utils.meta as meta
import hestia_utils.secrets as secrets
from hestia_utils.parser import Home, HomeResults


async def main() -> None:
    
    # Once a day at 7pm UTC, check some stuff and send an alert if necessary
    if datetime.now().hour == 19 and datetime.now().minute < 4:
        message = ""
        if db.get_dev_mode():
            message += "\n\nDev mode is enabled"
        if db.get_scraper_halted() and 'dev' not in meta.APP_VERSION:
            message += "\n\nScraper is halted"
    
        # Check if the donation link is expiring soon
        # Expiry of Tikkie links is 14 days, start warning after 13
        last_updated = db.get_donation_link_updated()
        if datetime.now() - last_updated >= timedelta(days=13):
            message += "\n\nDonation link expiring soon, use /setdonate"
            
        if message:
            await meta.BOT.send_message(text=message[2:], chat_id=secrets.OWN_CHAT_ID)

    # Once a week, Friday 6pm UTC, send all who subscribed three weeks ago a thanks with a donation link reminder
    if datetime.now().weekday() == 4 and datetime.now().hour == 18 and datetime.now().minute < 4:
        if db.get_dev_mode():
            logging.warning("Dev mode is enabled, not broadcasting thanks messages")
        else:
            subs = db.fetch_all("""
                SELECT * FROM hestia.subscribers 
                WHERE telegram_enabled = true 
                AND date_added BETWEEN NOW() - INTERVAL '4 weeks' AND NOW() - INTERVAL '3 weeks'
            """)

            donation_link = db.get_donation_link()
            logging.warning(f"Broadcasting thanks message to {len(subs)} subscribers")
            for sub in subs:
                sleep(1/29)  # avoid rate limit (broadcasting to max 30 users per second)
                message = rf"""Thanks for using Hestia, I\'ve put a lot of work into it and I hope it\'s helping you out\!
                
Moving is expensive enough and similar scraping services start at like €20/month\. Hopefully Hestia has helped you save some money\! With this open Tikkie you could use some of those savings to [buy me a beer]({donation_link}) {meta.LOVE_EMOJI}

Good luck in your search\!"""
                try:
                    await meta.BOT.send_message(text=message, chat_id=sub["telegram_id"], parse_mode="MarkdownV2", disable_web_page_preview=True)
                except BaseException as e:
                    logging.warning(f"Exception while broadcasting thanks message to {sub['telegram_id']}: {repr(e)}")
                    continue
    
    if not db.get_scraper_halted():
        scrape_start_ts = datetime.now()
        for target in db.fetch_all("SELECT * FROM hestia.targets WHERE enabled = true"):
            try:
                await scrape_site(target)
            except BaseException as e:
                error = f"[{target['agency']} ({target['id']})] {repr(e)}"
                logging.error(error)
                if "Connection reset by peer" not in error:
                    await meta.BOT.send_message(text=error, chat_id=secrets.OWN_CHAT_ID)
        scrape_duration = datetime.now() - scrape_start_ts
        logging.warning(f"Scrape took {scrape_duration.total_seconds()} seconds")
    else:
        logging.warning("Scraper is halted")


async def broadcast(homes: list[Home]) -> None:
    subs = set()
    
    if db.get_dev_mode():
        subs = db.fetch_all("SELECT * FROM hestia.subscribers WHERE telegram_enabled = true AND user_level > 1")
    else:
        subs = db.fetch_all("SELECT * FROM hestia.subscribers WHERE telegram_enabled = true")
        
    # Create dict of agencies and their pretty names
    agencies = db.fetch_all("SELECT agency, user_info FROM hestia.targets")
    agencies = dict([(a["agency"], a["user_info"]["agency"]) for a in agencies])
    
    for home in homes:
        for sub in subs:
            # Apply filters
            sqm_ok = (sub["filter_min_sqm"] == 0) or (home.sqm == -1) or (home.sqm >= sub["filter_min_sqm"])
            if (home.price >= sub["filter_min_price"] and home.price <= sub["filter_max_price"]) and \
               (home.city.lower() in sub["filter_cities"]) and \
               (home.agency in sub["filter_agencies"]) and \
               sqm_ok:

                message = f"{meta.HOUSE_EMOJI} {home.address}, {home.city}\n"
                message += f"{meta.EURO_EMOJI} €{home.price}/m\n"
                if home.sqm > 0:
                    message += f"{meta.SQM_EMOJI} {home.sqm} m\u00b2\n"
                message += "\n"
                message = meta.escape_markdownv2(message)
                message += f"{meta.LINK_EMOJI} [{agencies[home.agency]}]({home.url})"
                
                try:
                    await meta.BOT.send_message(text=message, chat_id=sub["telegram_id"], parse_mode="MarkdownV2")
                except Forbidden as e:
                    # This means the user deleted their account or blocked the bot, so disable them
                    db.disable_user(sub["telegram_id"])
                    logging.warning(f"Removed subscriber with Telegram id {str(sub['telegram_id'])} due to broadcast failure: {repr(e)}")
                except Exception as e:
                    # Log any other exceptions
                    logging.warning(f"Failed to broadcast to {sub['telegram_id']}: {repr(e)}")


async def scrape_site(target: dict) -> None:
    if target["method"] == "GET":
        r = requests.get(target["queryurl"], headers=target["headers"])
    elif target["method"] == "POST":
        r = requests.post(target["queryurl"], json=target["post_data"], headers=target["headers"])
    elif target["method"] == "POST_NDJSON":
        post_data = "\n".join(json.dumps(obj, separators=(",", ":")) for obj in target["post_data"]) + "\n"
        r = requests.post(target["queryurl"], data=post_data, headers=target["headers"])
    else:
        raise ValueError(f"Unknown method {target['method']} for target id {target['id']}")
        
    if r.status_code == 200:
        prev_homes: list[Home] = []
        new_homes: list[Home] = []
        
        # Check retrieved homes against previously scraped homes (of the last 6 months)
        for home in db.fetch_all("SELECT address, city FROM hestia.homes WHERE date_added > now() - interval '180 day'"):
            prev_homes.append(Home(home["address"], home["city"]))
        for home in HomeResults(target["agency"], r):
            if home not in prev_homes:
                new_homes.append(home)

        # Write new homes to database
        for home in new_homes:
            db.add_home(home.url,
                        home.address,
                        home.city,
                        home.price,
                        home.agency,
                        datetime.now().isoformat(),
                        home.sqm)

        await broadcast(new_homes)
    else:
        raise ConnectionError(f"Got a non-OK status code: {r.status_code}")
    

if __name__ == '__main__':
    run(main())

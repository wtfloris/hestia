import hestia
import logging
import requests
import secrets
from datetime import datetime
from asyncio import run

async def main():
    if hestia.check_scraper_halted():
        logging.warning("Scraper is halted.")
        exit()
        
    targets = hestia.query_db("SELECT * FROM hestia.targets WHERE enabled = true")

    for target in targets:
        try:
            await scrape_site(target)
        except BaseException as e:
            error = f"[{target['agency']} ({target['id']})] {repr(e)}"
            logging.error(error)
            
            if "Connection reset by peer" not in error:
                await hestia.BOT.send_message(text=error, chat_id=secrets.OWN_CHAT_ID)

async def broadcast(homes):
    subs = set()
    
    if hestia.check_dev_mode():
        subs = hestia.query_db("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true AND user_level > 1")
    else:
        subs = hestia.query_db("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true")
    
    for home in homes:
        for sub in subs:
            
            if home.price < sub["filter_min_price"] or home.price > sub["filter_max_price"]:
                continue
            
            if home.city.lower() not in sub["filter_cities"]:
                continue
            
            message = f"{hestia.HOUSE_EMOJI} {home.address}, {home.city}\n"
            message += f"{hestia.EURO_EMOJI} €{home.price}/m\n"
            message += f"{hestia.LINK_EMOJI} [Link]({home.url})"
            
            # If a user blocks the bot, this would throw an error and kill the entire broadcast
            try:
                await hestia.BOT.send_message(text=message, chat_id=sub["telegram_id"], parse_mode="MarkdownV2")
            except:
                pass

async def scrape_site(target):
    agency = target["agency"]
    url = target["queryurl"]
    headers = target["headers"]
    
    if target["method"] == "GET":
        r = requests.get(url, headers=headers)
    elif target["method"] == "POST":
        r = requests.post(url, json=target["post_data"], headers=headers)
        
    if not r.status_code == 200:
        raise ConnectionError(f"Got a non-OK status code: {r.status_code}")
    
    prev_homes = []
    new_homes = []
    
    # Check retrieved homes against previously scraped homes
    for home in hestia.query_db("SELECT address, city FROM hestia.homes WHERE agency = %s", params=[agency]):
        prev_homes.append(hestia.Home(home["address"], home["city"]))
    
    for home in hestia.HomeResults(agency, r):
        if home not in prev_homes:
            new_homes.append(home)

    # Write new homes to database
    for home in new_homes:
        hestia.query_db("INSERT INTO hestia.homes VALUES (%s, %s, %s, %s, %s, %s)",
            (home.url,
            home.safe_address,
            home.safe_city,
            home.price,
            home.agency,
            datetime.now().isoformat()))

    await broadcast(new_homes)
    

if __name__ == '__main__':
    run(main())

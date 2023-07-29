import hestia
import logging
import os
import requests
import pickle
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from bs4 import BeautifulSoup
from datetime import datetime
from asyncio import run
from secrets import OWN_CHAT_ID
from time import sleep

async def main():
    if hestia.check_scraper_halted():
        logging.warning("Scraper is halted.")
        exit()
        
    targets = hestia.query_db("SELECT * FROM hestia.targets WHERE enabled = true")

    for target in targets:
        try:
            await scrape_site(target)
        except BaseException as e:
            error = f"[{agency} ({id})] {repr(e)}"
            logging.error(error)
            await hestia.BOT.send_message(text=error, chat_id=OWN_CHAT_ID)

async def broadcast(homes):
    subs = set()
    
    if hestia.check_dev_mode():
        subs = hestia.query_db("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true AND user_level > 1")
    else:
        subs = hestia.query_db("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true")

    for home in homes:
        for sub in subs:
            # TODO check if home is within user parameters
            
            message = f"{hestia.HOUSE_EMOJI} {home['address']}, {home['city']}\n"
            message += f"{hestia.LINK_EMOJI} {home['url']}"
            
            # If a user blocks the bot, this would throw an error and kill the entire broadcast
            try:
                await hestia.BOT.send_message(text=message, chat_id=sub["telegram_id"])
            except:
                pass

async def scrape_site(target):
    agency = target["agency"]
    url = target["queryurl"]
    method = target["method"]
    
    if method == "GET":
        r = requests.get(url)
    elif method == "POST":
        r = requests.post(url, json=target["post_data"], headers=target["headers"])
    
    prev_homes = []
    new_homes = []
    
    # Because of the diversity in the scraped data, we use the URL as an ID for a home
    for home in hestia.query_db(f"SELECT url FROM hestia.homes WHERE agency = '{agency}'"):
        prev_homes.append(home["url"])
    
    if not r.status_code == 200:
        raise ConnectionError(f"Got a non-OK status code: {r.status_code}.")
        
    if agency == "vesteda":
        results = json.loads(r.content)["results"]["items"]
        
        for res in results:
            # Filter non-available properties
            # Status 0 seems to be that the property is a project/complex
            if res["status"] != 1:
                continue
            
            home = {}
            home["address"] = f"{res['street']} {res['houseNumber']}"
            if res["houseNumberAddition"] is not None:
                home["address"] += f" {res['houseNumberAddition']}"
            home["city"] = res["city"]
            home["url"] = "https://vesteda.com" + res["url"]
            home["price"] = int(res["priceUnformatted"])
            if home["url"] not in prev_homes:
                new_homes.append(home)
                
    elif agency == "vbt":
        results = json.loads(r.content)["houses"]
        
        for res in results:
            # Filter Bouwinvest results to not have double results
            if res["isBouwinvest"]:
                continue
            
            home = {}
            home["address"] = res["address"]["house"]
            home["city"] = res["address"]["city"]
            home["url"] = res["source"]["externalLink"]
            home["price"] = res["prices"]["rental"]["price"]
            if home["url"] not in prev_homes:
                new_homes.append(home)
        
    elif agency == "alliantie":
        results = json.loads(r.content)["data"]
        
        for res in results:
            # Filter results not in selection because why the FUCK would you include
            # parameters and then not actually use them in your FUCKING API
            if not res["isInSelection"]:
                continue
                
            home = {}
            home["address"] = res["address"]
            # this is a dirty hack because what website with rental homes does not
            # include the city AT ALL in their FUCKING API RESPONSES
            city_start = res["url"].index('/') + 1
            city_end = res["url"][city_start:].index('/') + city_start
            home["city"] = res["url"][city_start:city_end].capitalize()
            home["url"] = "https://ik-zoek.de-alliantie.nl/" + res["url"].replace(" ", "%20")
            home["price"] = res["price"][2:].replace('.', '')
            if home["url"] not in prev_homes:
                new_homes.append(home)
        
    elif agency == "woningnet":
        results = json.loads(r.content)["Resultaten"]
        
        for res in results:
            # Filter senior & family priority results
            if res["WoningTypeCssClass"] == "Type03":
                continue
            
            home = {}
            home["address"] = res["Adres"]
            home["city"] = res["PlaatsWijk"].split('-')[0][:-1]
            home["url"] = "https://www.woningnetregioamsterdam.nl" + res["AdvertentieUrl"]
            home["price"] = res["Prijs"][2:-3].replace('.', '')
            if home["url"] not in prev_homes:
                new_homes.append(home)
    
    elif agency == "bouwinvest":
        results = json.loads(r.content)["data"]

        for res in results:
            # Filter non-property results
            if res["class"] == "Project":
                continue

            home = {}
            home["address"] = res["name"]
            home["city"] = res["address"]["city"]
            home["url"] = res["url"]
            home["price"] = res["price"]["price"]
            if home["url"] not in prev_homes:
                new_homes.append(home)

    elif agency == "ikwilhuren":
        results = BeautifulSoup(r.content, "html.parser").find_all("li", class_="search-result")

        for res in results:
            home = {}
            home["address"] = str(res.find(class_="street-name").contents[0])
            home["city"] = ''.join(str(res.find(class_="plaats").contents[0]).split(' ')[2:])
            home["url"] = res.find(class_="search-result-title").a["href"]
            home["price"] = str(res.find(class_="page-price").contents[0])[1:].replace('.', '')
            if home["url"] not in prev_homes:
                new_homes.append(home)

    # Write new homes to database
    for home in new_homes:
        hestia.query_db(f"INSERT INTO hestia.homes VALUES ('{home['url']}', '{home['address']}', '{home['city']}', '{home['price']}', '{agency}', '{datetime.now().isoformat()}')")

    await broadcast(new_homes)


if __name__ == '__main__':
    run(main())

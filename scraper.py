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

async def main():
    if hestia.check_scraper_halted():
        logging.warning("Scraper is halted.")
        exit()
        
    targets = hestia.query_db("SELECT * FROM hestia.targets WHERE enabled = true")

    for target in targets:
        try:
            await scrape_site(target)
        except BaseException as e:
            await handle_exception(target["id"], target["agency"], e)

async def handle_exception(id, agency, e):
    error = f"[{id}: {agency}] {repr(e)}"
    last_error = "["

    # If the error was already logged, do not log it again
    # This is to prevent the same error popping up every time cron runs the scraper
    if os.path.exists(hestia.WORKDIR + "error.log"):
        with open(hestia.WORKDIR + "error.log", 'r') as err:
            last_error = err.readlines()[-1]

    if last_error[last_error.index('['):-1] != error:
        logging.error(error)
        await hestia.BOT.send_message(text=error, chat_id=OWN_CHAT_ID)

async def broadcast(new_homes):
    subs = set()
    
    if hestia.check_dev_mode():
        subs = hestia.query_db("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true AND user_level > 1")
    else:
        subs = hestia.query_db("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true")

    for home in new_homes:
        for sub in subs:
            # TODO check if home is within user parameters
            
            message = f"{hestia.HOUSE_EMOJI} {home[0]}\n"
            message += f"{hestia.LINK_EMOJI} {home[1]}"
            
            # If a user blocks the bot, this would throw an error and kill the entire broadcast
            try:
                await hestia.BOT.send_message(text=message, chat_id=sub["telegram_id"])
            except:
                logging.warning(f"Error transmitting to user {sub['id']}")
                pass

async def scrape_site(target):
    agency = target["agency"]
    url = target["queryurl"]
    method = target["method"]
    
    if method == "GET":
        r = requests.get(url)
    elif method == "POST":
        r = requests.post(url, json=target["post_data"], headers=target["headers"])
    
    prev_homes = set()
    new_homes = set()
    
    # Create savefile if it does not exist
#    if not os.path.exists(hestia.WORKDIR + savefile):
#        with open(hestia.WORKDIR + savefile, 'wb') as w:
#            pickle.dump(set([]), w)

    # Get the previously broadcasted homes
#    with open(hestia.WORKDIR + savefile, 'rb') as prev_homes_file:
#        prev_homes = pickle.load(prev_homes_file)
        
    # TODO get previously broadcasted homes of current agency from db
    
    for home in hestia.query_db(f"SELECT url FROM hestia.homes WHERE agency = '{agency}'"):
        prev_homes.add(home["url"])
    
    if not r.status_code == 200:
        raise ConnectionError(f"Got a non-OK status code: {r.status_code}.")
        
    if agency == "vesteda":
        results = json.loads(r.content)["results"]["items"]
        
        for res in results:
            # Filter non-available properties
            # Status 0 seems to be that the property is a project/complex
            if res["status"] != 1:
                continue
            print()
            print()
            print()
            print(agent)
            print(res)
            print()
            print()
            print()
            break
            address = f"{res['street']} {res['houseNumber']}"
            if res["houseNumberAddition"] is not None:
                address += f"{res['houseNumberAddition']}"
            url = "https://vesteda.com" + res["url"]
            if url not in prev_homes:
                new_homes.add((address, url))
                prev_homes.add(address)
                
    elif agency == "vbt":
        results = json.loads(r.content)["houses"]
        
        for res in results:
            # Filter Bouwinvest results to not have double results
            if res["isBouwinvest"]:
                continue
        
            address = res["address"]["house"]
            city = res["address"]["city"]
            url = res["source"]["externalLink"]
            if url not in prev_homes:
                new_homes.add((address, url))
                prev_homes.add(address)
        
    elif agency == "alliantie":
        results = json.loads(r.content)["data"]
        
        for res in results:
            # Filter results not in selection because why the FUCK would you include
            # parameters and then not actually use them in your FUCKING API
            if not res["isInSelection"]:
                continue
            print()
            print()
            print()
            print(agent)
            print(res)
            print()
            print()
            print()
            break
                
            address = res["address"]
            url = "https://ik-zoek.de-alliantie.nl/" + res["url"].replace(" ", "%20")
            if url not in prev_homes:
                new_homes.add((address, url))
                prev_homes.add(address)
        
    elif agency == "woningnet":
        results = json.loads(r.content)["Resultaten"]
        
        for res in results:
            # Filter senior & family priority results
            if res["WoningTypeCssClass"] == "Type03":
                continue
            print()
            print()
            print()
            print(agent)
            print(res)
            print()
            print()
            print()
            break
                
            address = res["Adres"]
            url = "https://www.woningnetregioamsterdam.nl" + res["AdvertentieUrl"]
            if url not in prev_homes:
                new_homes.add((address, url))
                prev_homes.add(address)
    
    elif agency == "bouwinvest":
        results = json.loads(r.content)["data"]

        for res in results:
            # Filter non-property results
            if res["class"] == "Project":
                continue
            print()
            print()
            print()
            print(agent)
            print(res)
            print()
            print()
            print()
            break

            address = res["name"]
            url = res["url"]
            if url not in prev_homes:
                new_homes.add((address, url))
                prev_homes.add(address)

    elif agency == "ikwilhuren":
        results = BeautifulSoup(r.content, "html.parser").find_all("li", class_="search-result")

        for res in results:
            print()
            print()
            print()
            print(agent)
            print(res)
            print()
            print()
            print()
            break
            address = str(res.find(class_="street-name").contents[0])
            url = res.find(class_="search-result-title").a["href"]
            if url not in prev_homes:
                new_homes.add((address, url))
                prev_homes.add(address)

    # Write new homes to savefile
    with open(hestia.WORKDIR + savefile, 'wb') as prev_homes_file:
        pickle.dump(prev_homes, prev_homes_file)
        
    # TODO write new homes to db

    await broadcast(new_homes)


if __name__ == '__main__':
    run(main())

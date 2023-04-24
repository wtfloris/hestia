import os
import telegram
import requests, pickle, json
from bs4 import BeautifulSoup
from datetime import datetime
from asyncio import run
from targets import targets
from secrets import OWN_CHAT_ID, TOKEN
from hestia import WORKDIR

BOT = telegram.Bot(TOKEN)

HOUSE_EMOJI = "\U0001F3E0"
LINK_EMOJI = "\U0001F517"

async def main():
    for item in targets:
        try:
            await scrape_site(item)
        except BaseException as e:
            await handle_exception(item["site"], item["savefile"], e)

async def handle_exception(site, savefile, e):
    error = f"[{site}: {savefile}] {repr(e)}"
    last_error = "["

    # If the error was already logged, do not log it again
    # This is to prevent the same error popping up every time cron runs the scraper
    if os.path.exists(WORKDIR + "error.log"):
        with open(WORKDIR + "error.log", 'r') as err:
            last_error = err.readlines()[-1]

    if last_error[last_error.index('['):-1] != error:
        with open(WORKDIR + "error.log", 'a') as log:
            log.write(f"{datetime.now()} {error}\n")
        await BOT.send_message(text=error, chat_id=OWN_CHAT_ID)

async def broadcast(new_homes):
    with open(WORKDIR + "subscribers", 'rb') as subscribers_file:
        subs = pickle.load(subscribers_file)

    for home in new_homes:
        for sub in subs:
            # If a user blocks the bot, this would throw an error and kill the entire broadcast
            try:
                message = f"{HOUSE_EMOJI} {home[0]}\n"
                message += f"{LINK_EMOJI} {home[1]}"
                await BOT.send_message(text=message, chat_id=sub)
            except:
                continue

async def scrape_site(item):
    site = item["site"]
    savefile = item["savefile"]
    url = item["url"]
    method = item["method"]
    
    if method == "GET":
        r = requests.get(url)
    elif method == "POST":
        r = requests.post(url, json=item["data"], headers=item["headers"])
    
    houses = []
    prev_homes = set()
    new_homes = set()
    
    # Create savefile if it does not exist
    if not os.path.exists(WORKDIR + savefile):
        with open(WORKDIR + savefile, 'wb') as w:
            pickle.dump(set([]), w)

    # Get the previously broadcasted homes
    with open(WORKDIR + savefile, 'rb') as prev_homes_file:
        prev_homes = pickle.load(prev_homes_file)
    
    if not r.status_code == 200:
        raise ConnectionError(f"Got a non-OK status code: {r.status_code}.")
        
    if site == "alliantie":
        results = json.loads(r.content)["data"]
        
        for res in results:
            # Filter results not in selection because why the FUCK would you include
            # parameters and then not actually use them in your FUCKING API
            if not res["isInSelection"]:
                continue
                
            house = res["address"]
            link = "https://ik-zoek.de-alliantie.nl/" + res["url"].replace(" ", "%20")
            if house not in prev_homes:
                new_homes.add((house, link))
                prev_homes.add(house)
        
    elif site == "woningnet":
        results = json.loads(r.content)["Resultaten"]
        
        for res in results:
            # Filter senioren & gezin priority results
            if res["WoningTypeCssClass"] == "Type03":
                continue
                
            house = res["Adres"]
            link = "https://www.woningnetregioamsterdam.nl" + res["AdvertentieUrl"]
            if house not in prev_homes:
                new_homes.add((house, link))
                prev_homes.add(house)
    
    elif site == "bouwinvest":
        results = json.loads(r.content)["data"]

        for res in results:
            # Filter non-property results
            if res["class"] == "Project":
                continue

            house = res["name"]
            link = res["url"]
            if house not in prev_homes:
                new_homes.add((house, link))
                prev_homes.add(house)

    elif site == "ikwilhuren":
        results = BeautifulSoup(r.content, "html.parser").find_all("li", class_="search-result")

        for res in results:
            house = str(res.find(class_="street-name").contents[0])
            link = res.find(class_="search-result-title").a["href"]
            if house not in prev_homes:
                new_homes.add((house, link))
                prev_homes.add(house)
     
    # Now only offered through Woningnet
#    if site == "eh":
#        results = BeautifulSoup(r.content, 'html.parser').find_all(class_="column-flex-box")
#
#        for res in results:
#            house = str(res.find(class_="content").find("h3").contents[0])
#            link = 'https://www.eigenhaard.nl' + res.a['href']
#            if house not in prev_homes:
#                new_homes.add((house, link))
#                prev_homes.add(house)

    # Write new homes to savefile
    with open(WORKDIR + savefile, 'wb') as prev_homes_file:
        pickle.dump(prev_homes, prev_homes_file)

    await broadcast(new_homes)


if __name__ == '__main__':
    run(main())

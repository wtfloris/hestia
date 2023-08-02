import psycopg2
import telegram
import logging
import json
import requests
from psycopg2.extras import RealDictCursor
from bs4 import BeautifulSoup
from secrets import OWN_CHAT_ID, TOKEN, DB


class Home:
    def __init__(self, address='', city='', url='', agency='', price=-1):
        self.address = address
        self.city = city
        self.url = url
        self.agency = agency
        self.price = price
        
    def __repr__(self):
        return str(self)
        
    def __str__(self):
        return f"{self.address}, {self.city} ({self.agency.title()})"
        
    def __eq__(self, other):
        if self.address.lower() == other.address.lower():
            if self.city.lower() == other.city.lower():
                return True
        return False
    
    @property
    def city(self):
        return self._raw_city
        
    @city.setter
    def city(self, city):
        self._raw_city = city
        self.safe_city = city.replace("'", "''")
    
    @property
    def address(self):
        return self._raw_address
        
    @address.setter
    def address(self, address):
        self._raw_address = address
        self.safe_address = address.replace("'", "''")
        

class HomeResults:
    def __getitem__(self, n):
        return self.homes[n]
            
    def __repr__(self):
        return str([home for home in self.homes])
    
    def __init__(self, source, raw):
        if not isinstance(source, str):
            raise ValueError(f"Expected string as first argument, got {type(source)}")
        if not isinstance(raw, requests.models.Response):
            raise ValueError(f"Expected requests.models.Response object as second argument, got {type(raw)}")
    
        self.homes = []
    
        if source == "vesteda":
            self.parse_vesteda(raw)
        elif source == "ikwilhuren":
            self.parse_ikwilhuren(raw)
        elif source == "bouwinvest":
            self.parse_bouwinvest(raw)
        elif source == "alliantie":
            self.parse_alliantie(raw)
        elif source == "vbt":
            self.parse_vbt(raw)
        elif source == "woningnet":
            self.parse_woningnet(raw)
        else:
            raise ValueError(f"Unknown source: {source}")
    
    def parse_vesteda(self, r):
        results = json.loads(r.content)["results"]["items"]
            
        for res in results:
            # Filter non-available properties
            # Status 0 seems to be that the property is a project
            if res["status"] != 1:
                continue
                
            # I don't think seniors are really into Telegram
            if res["onlySixtyFivePlus"]:
                continue
            
            home = Home(agency="vesteda")
            home.address = f"{res['street']} {res['houseNumber']}"
            if res["houseNumberAddition"] is not None:
                home.address += f"{res['houseNumberAddition']}"
            home.city = res["city"]
            home.url = "https://vesteda.com" + res["url"]
            home.price = int(res["priceUnformatted"])
            self.homes.append(home)
            
    def parse_ikwilhuren(self, r):
        results = BeautifulSoup(r.content, "html.parser").find_all("li", class_="search-result")
    
        for res in results:
            # Filter rented properties
            if str(res.find(class_="page-price").contents[0]).lower() == "verhuurd":
                continue
        
            home = Home(agency="ikwilhuren")
            home.address = str(res.find(class_="street-name").contents[0])
            home.city = ''.join(str(res.find(class_="plaats").contents[0]).split(' ')[2:])
            home.url = res.find(class_="search-result-title").a["href"]
            home.price = int(str(res.find(class_="page-price").contents[0])[1:].replace('.', ''))
            self.homes.append(home)
        
    def parse_vbt(self, r):
        results = json.loads(r.content)["houses"]
        
        for res in results:
            # Filter Bouwinvest results to not have double results
            if res["isBouwinvest"]:
                continue
            
            home = Home(agency="vbt")
            home.address = res["address"]["house"]
            home.city = res["address"]["city"]
            home.url = res["source"]["externalLink"]
            home.price = int(res["prices"]["rental"]["price"])
            self.homes.append(home)
            
    def parse_alliantie(self, r):
        results = json.loads(r.content)["data"]
        
        for res in results:
            # Filter results not in selection because why the FUCK would you include
            # parameters and then not actually use them in your FUCKING API
            if not res["isInSelection"]:
                continue
                
            home = Home(agency="alliantie")
            home.address = res["address"]
            # this is a dirty hack because what website with rental homes does not
            # include the city AT ALL in their FUCKING API RESPONSES
            city_start = res["url"].index('/') + 1
            city_end = res["url"][city_start:].index('/') + city_start
            home.city = res["url"][city_start:city_end].capitalize()
            home.url = "https://ik-zoek.de-alliantie.nl/" + res["url"].replace(" ", "%20")
            home.price = int(res["price"][2:].replace('.', ''))
            self.homes.append(home)
            
    def parse_woningnet(self, r):
        results = json.loads(r.content)["Resultaten"]
        
        for res in results:
            # Filter senior & family priority results
            if res["WoningTypeCssClass"] == "Type03":
                continue
            
            home = Home(agency="woningnet")
            home.address = res["Adres"]
            home.city = res["PlaatsWijk"].split('-')[0][:-1]
            home.url = "https://www.woningnetregioamsterdam.nl" + res["AdvertentieUrl"]
            home.price = int(res["Prijs"][2:-3].replace('.', ''))
            self.homes.append(home)
            
    def parse_bouwinvest(self, r):
        results = json.loads(r.content)["data"]
    
        for res in results:
            # Filter non-property results
            if res["class"] == "Project":
                continue
    
            home = Home(agency="bouwinvest")
            home.address = res["name"]
            home.city = res["address"]["city"]
            home.url = res["url"]
            home.price = int(res["price"]["price"])
            self.homes.append(home)
            

def query_db(query, fetchOne=False):
# TODO error handling
    db = psycopg2.connect(database=DB["database"],
                            host=DB["host"],
                            user=DB["user"],
                            password=DB["password"],
                            port=DB["port"])
    
    cursor = db.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query)
    
    # Try, because not all queries will return data
    try:
        if fetchOne:
            result = cursor.fetchone()
        else:
            result = cursor.fetchall()
    except:
        result = None
    
    db.commit()
    cursor.close()
    db.close()
    
    return result


WORKDIR = query_db("SELECT workdir FROM hestia.meta", fetchOne=True)["workdir"]

logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s",
    level=logging.WARNING,
    filename=WORKDIR + "hestia.log"
)

BOT = telegram.Bot(TOKEN)

HOUSE_EMOJI = "\U0001F3E0"
LINK_EMOJI = "\U0001F517"

# The identifier of the used settings in the database (default = default)
SETTINGS_ID = "default"


def check_dev_mode():
    return query_db("SELECT devmode_enabled FROM hestia.meta", fetchOne=True)["devmode_enabled"]

def check_scraper_halted():
    return query_db("SELECT scraper_halted FROM hestia.meta", fetchOne=True)["scraper_halted"]

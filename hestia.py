import psycopg2
import telegram
import logging
import json
import requests
import re
from psycopg2.extras import RealDictCursor
from bs4 import BeautifulSoup
from secrets import TOKEN, DB


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
    def address(self):
        return self._address
        
    @address.setter
    def address(self, address):
        self._address = address
        
    @property
    def city(self):
        return self._parsed_city
        
    @city.setter
    def city(self, city):
        # Strip the trailing province if present
        if re.search(" \([a-zA-Z]{2}\)$", city):
            city = ' '.join(city.split(' ')[:-1])
    
        # Handle cities with two names and other edge cases
        if city.lower() in ["'s-gravenhage", "s-gravenhage"]:
            city = "Den Haag"
        elif city.lower() in ["'s-hertogenbosch", "s-hertogenbosch"]:
            city = "Den Bosch"
        elif city.lower() in ["alphen aan den rijn", "alphen a/d rijn"]:
            city = "Alphen aan den Rijn"
        elif city.lower() in ["koog aan de zaan", "koog a/d zaan"]:
            city = "Koog aan de Zaan"
        elif city.lower() in ["capelle aan den ijssel", "capelle a/d ijssel"]:
            city = "Capelle aan den IJssel"
        elif city.lower() in ["berkel-enschot", "berkel enschot"]:
            city = "Berkel-Enschot"
        elif city.lower() in ["oud-beijerland", "oud beijerland"]:
            city = "Oud-Beijerland"
        elif city.lower() in ["etten-leur", "etten leur"]:
            city = "Etten-Leur"
        elif city.lower() in ["nieuw vennep", "nieuw-vennep"]:
            city = "Nieuw-Vennep"
        elif city.lower() == "son en breugel":
            city = "Son en Breugel"
        elif city.lower() == "bergen op zoom":
            city = "Bergen op Zoom"
        elif city.lower() == "berkel en rodenrijs":
            city = "Berkel en Rodenrijs"
        elif city.lower() == "wijk bij duurstede":
            city = "Wijk bij Duurstede"
        elif city.lower() == "hoogvliet rotterdam":
            city = "Hoogvliet Rotterdam"
        elif city.lower() == "nederhorst den berg":
            city = "Nederhorst den Berg"
        elif city.lower() == "huis ter heide":
            city = "Huis ter Heide"
            
        self._parsed_city = city
        

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
        elif source == "krk":
            self.parse_krk(raw)
        elif source == "makelaarshuis":
            self.parse_makelaarshuis(raw)
        elif "woningnet_" in source:
            self.parse_woningnet_dak(raw, source.split("_")[1])
        elif source == "pararius":
            self.parse_pararius(raw)
        elif source == "funda":
            self.parse_funda(raw)
        elif source == "rebo":
            self.parse_rebo(raw)
        elif source == "nmg":
            self.parse_nmg(raw)
        elif source == "vbo":
            self.parse_vbo(raw)
        else:
            raise ValueError(f"Unknown source: {source}")
    
    def parse_vesteda(self, r):
        results = json.loads(r.content)["results"]["objects"]
            
        for res in results:
            # Filter non-available properties
            # Status 0 seems to be that the property is a project
            # Status > 1 seems to be unavailable
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
        results = BeautifulSoup(r.content, "html.parser").find_all("div", class_="card-woning")
    
        for res in results:
            # Filter "zorgwoningen"
            if "Zorgwoning" in res.get_text():
                continue
        
            home = Home(agency="ikwilhuren")
            home.address = str(res.find(class_="stretched-link").contents[0].strip())
            
            postcodecity = str(res.find(class_="card-body").contents[3].get_text())
            home.city = ' '.join(postcodecity.split(' ')[1:])
            
            # ikwilhuren lists some Bouwinvest properties, which have a full link attached
            link = res.find(class_="stretched-link")["href"]
            if "wonenbijbouwinvest.nl" in link:
                home.url = link
            else:
                home.url = "https://ikwilhuren.nu" + link
                
            home.price = int(str(res.find(class_="fw-bold")).split(' ')[2].replace('.', '')[:-2])
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
            
    def parse_woningnet_dak(self, r, regio):
        results = json.loads(r.content)["data"]["PublicatieLijst"]["List"]
        
        for res in results:
            # Filter seniorenwoningen and items without prices
            if "Seniorenwoning" in res["PublicatieLabel"] or res["Eenheid"]["Brutohuur"] == "0.0":
                continue
            
            home = Home(agency=f"woningnet_{regio}")
            home.address = f"{res['Adres']['Straatnaam']} {res['Adres']['Huisnummer']}"
            if res["Adres"]["HuisnummerToevoeging"]:
                home.address = f"{home.address} {res['Adres']['HuisnummerToevoeging']}"
            home.city = res["Adres"]["Woonplaats"]
            home.url = f"https://{regio}.mijndak.nl/HuisDetails?PublicatieId={res['Id']}"
            home.price = int(float(res["Eenheid"]["Brutohuur"]))
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
    
    def parse_krk(self, r):
        results = json.loads(r.content)["objects"]
    
        for res in results:
            # Filter non-rental and unavailable properties
            if res["buy_or_rent"] != "rent" or res["availability_status"].lower() != "beschikbaar":
                continue
    
            home = Home(agency="krk")
            home.address = res["short_title"]
            home.city = res["place"]
            home.url = res["url"]
            home.price = int(res["rent_price"])
            self.homes.append(home)
            
    def parse_makelaarshuis(self, r):
        results = BeautifulSoup(r.content, "html.parser").find_all("div", class_="object")
    
        for res in results:
            # Filter rented properties
            if 'rented' in str(res.find(class_="object_status")):
                continue
        
            home = Home(agency="makelaarshuis")
            home.address = str(res.find("span", class_="street").contents[0])
            home.city = str(res.find("span", class_="locality").contents[0])
            home.url = "https://yourexpatbroker.nl" + res.find("a", class_="saletitle")["href"].split('?')[0]
            home.price = int(str(res.find("span", class_="obj_price").contents[0]).split('€')[1][1:6].split(',')[0].replace('.', ''))
            self.homes.append(home)
            
    def parse_pararius(self, r):
        results = BeautifulSoup(r.content, "html.parser").find_all("section", class_="listing-search-item--for-rent")
        
        for res in results:
        
            home = Home(agency="pararius")
            raw_address = str(res.find("a", class_="listing-search-item__link--title").contents[0].strip())
        
            # A lot of properties on Pararius don't include house numbers, so it's impossible to keep track of them because
            # right now homes are tracked by address, not by URL (which has its own downsides).
            # This is probably not 100% reliable either, but it's close enough.
            if not re.search("[0-9]", raw_address):
                continue
            if re.search("^[0-9]", raw_address): # Filter "1e Foobarstraat", etc.
                continue
                
            home.address = ' '.join(raw_address.split(' ')[1:]) # All items start with one of ["Appartement", "Huis", "Studio", "Kamer"]
            raw_city = res.find("div", class_="listing-search-item__sub-title'").contents[0].strip()
            home.city = ' '.join(raw_city.split(' ')[2:]).split('(')[0].strip() # Don't ask
            home.url = "https://pararius.nl" + res.find("a", class_="listing-search-item__link--title")['href']
            raw_price = res.find("div", class_="listing-search-item__price").contents[0].strip().replace('\xa0', '')

            # If unable to cast to int, the price is not available so skip the listing
            try:
                home.price = int(raw_price[1:].split(' ')[0].replace('.', ''))
            except:
                continue

            self.homes.append(home)
            
    def parse_funda(self, r):
        results = json.loads(r.content)["search_result"]["hits"]["hits"]
        
        for res in results:
            # Some listings don't have house numbers, so skip
            if "house_number" not in res["_source"]["address"].keys():
                continue
            # Some listings don't have a rent_price, skip as well
            if "rent_price" not in res["_source"]["price"].keys():
                continue
        
            home = Home(agency="funda")
            
            home.address = f"{res['_source']['address']['street_name']} {res['_source']['address']['house_number']}"
            if "house_number_suffix" in res["_source"]["address"].keys():
                suffix = res["_source"]["address"]["house_number_suffix"]
                if '-' not in suffix and '+' not in suffix:
                    suffix = f" {suffix}"
                home.address += f"{suffix}"
            
            home.city = res["_source"]["address"]["city"]
            home.url = "https://funda.nl" + res["_source"]["object_detail_page_relative_url"]
            home.price = res["_source"]["price"]["rent_price"][0]
            
            self.homes.append(home)
            
    # I love websites with (accidental) public API endpoints and proper JSON
    def parse_rebo(self, r):
        results = json.loads(r.content)["hits"]
        for res in results:
            home = Home(agency="rebo")
            home.address = res["address"]
            home.city = res["city"]
            home.url = "https://www.rebogroep.nl/nl/aanbod/" + res["slug"]
            home.price = int(res["price"])
            self.homes.append(home)

    def parse_nmg(self, r):
        results = [map_item.get("template", "") for map_item in json.loads(r.content)["maps"]]
        for res in results:
            soup = BeautifulSoup(res, "html.parser")
            home = Home(agency="nmg")
            home.address = soup.select_one('.house__heading h2').text.strip().split('\t\t\t\t')[0]
            home.city = soup.select_one('.house__heading h2 span').text.strip()
            home.url = soup.select_one('.house__overlay')['href']
            # Remove all non-numeric characters from the price
            rawprice = soup.select_one('.house__list-item .house__icon--value + span').text.strip()
            home.price = int(re.sub(r'\D', '', rawprice))
            self.homes.append(home)

    def parse_vbo(self, r):
        results = BeautifulSoup(r.content, "html.parser").find_all("a", class_="propertyLink")
        for res in results:
            home = Home(agency="vbo")
            home.url = res["href"]
            home.address = res.select_one(".street").text
            home.city = res.select_one(".city").text
            rawprice = res.select_one(".price").text
            end = rawprice.index(",") # Every price is terminated with a trailing ,
            home.price = int(rawprice[2:end].replace(".", ""))
            self.homes.append(home)


def query_db(query, params=[], fetchOne=False):
# TODO error handling
    db = psycopg2.connect(database=DB["database"],
                            host=DB["host"],
                            user=DB["user"],
                            password=DB["password"],
                            port=DB["port"])
    
    cursor = db.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)
    
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

def escape_markdownv2(text):
    text = text.replace('.', '\.')
    text = text.replace('!', '\!')
    text = text.replace('+', '\+')
    text = text.replace('-', '\-')
    text = text.replace('*', '\*')
    return text

WORKDIR = query_db("SELECT workdir FROM hestia.meta", fetchOne=True)["workdir"]

logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s",
    level=logging.WARNING,
    filename=WORKDIR + "hestia.log"
)

BOT = telegram.Bot(TOKEN)

HOUSE_EMOJI = "\U0001F3E0"
LINK_EMOJI = "\U0001F517"
EURO_EMOJI = "\U0001F4B6"
LOVE_EMOJI = "\U0001F970"
CHECK_EMOJI = "\U00002705"
CROSS_EMOJI = "\U0000274C"

# The identifier of the used settings in the database (default = default)
SETTINGS_ID = "default"

# The Dockerfile replaces this with the git commit id
APP_VERSION = ''

def check_dev_mode():
    return query_db("SELECT devmode_enabled FROM hestia.meta", fetchOne=True)["devmode_enabled"]

def check_scraper_halted():
    return query_db("SELECT scraper_halted FROM hestia.meta", fetchOne=True)["scraper_halted"]

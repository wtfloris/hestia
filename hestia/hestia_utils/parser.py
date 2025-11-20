import re
import csv
import json
import chompjs
import logging
import requests
from urllib import parse
from bs4 import BeautifulSoup


class Home:
    def __init__(self, address: str = '', city: str = '', url: str = '', agency: str = '', price: int = -1):
        self.address = address
        self.city = city
        self.url = url
        self.agency = agency
        self.price = price
        
    def __repr__(self) -> str:
        return str(self)
        
    def __str__(self) -> str:
        return f"{self.address}, {self.city} ({self.agency.title()})"
        
    def __eq__(self, other) -> bool:
        if self.address.lower() == other.address.lower():
            if self.city.lower() == other.city.lower():
                return True
        return False
    
    @property
    def address(self) -> str:
        return self._address
        
    @address.setter
    def address(self, address: str) -> None:
        self._address = address
        
    @property
    def city(self) -> str:
        return self._parsed_city
        
    @city.setter
    def city(self, city: str) -> None:
        # Strip the trailing province if present
        if re.search(r" \([a-zA-Z]{2}\)$", city):
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
    def __getitem__(self, n: int) -> Home:
        return self.homes[n]
            
    def __repr__(self):
        return str([home for home in self.homes])
    
    def __init__(self, source: str, raw: requests.models.Response):
        self.homes: list[Home] = []
        if source == "vesteda":
            self.parse_vesteda(raw)
        elif source == "bouwinvest":
            self.parse_bouwinvest(raw)
        elif source == "alliantie":
            self.parse_alliantie(raw)
        elif source == "vbt":
            self.parse_vbt(raw)
        elif source == "krk":
            self.parse_krk(raw)
        elif source == "woonmatchwaterland":
            self.parse_woonmatchwaterland(raw)
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
        elif source == "atta":
            self.parse_atta(raw)
        elif source == "ooms":
            self.parse_ooms(raw)
        elif source == "woonzeker":
            self.parse_woonzeker(raw)
        elif source == "woonin":
            self.parse_woonin(raw)
        elif source == "woonnet_rijnmond":
            self.parse_woonnet_rijnmond(raw)
        elif source == 'entree':
            self.parse_entree(raw)
        elif "hexia_" in source:
            self.parse_hexia(raw, source.split("_")[1])
        elif source == "123wonen":
            self.parse_123wonen(raw)
        else:
            raise ValueError(f"Unknown source: {source}")

    def parse_hexia(self, r: requests.models.Response, corp: str):
        results = json.loads(r.content)["data"]

        for res in results:
            # Filter out non-rentable properties
            if not res['rentBuy'] == 'Huur':
                continue
            # Filter out listings that don't have all info
            if (
                "city" not in res
                or "name" not in res["city"]
                or "street" not in res
                or "houseNumber" not in res
                or "netRent" not in res 
                or "urlKey" not in res
            ):
                continue
            
            home = Home(agency=f"hexia_{corp}")
            home.city = res['city']['name']

            # If there is an addition to the housenumber defined, format with that instead
            if "houseNumberAddition" in res and res['houseNumberAddition']:
                home.address = f"{res['street']} {res['houseNumber']} {res['houseNumberAddition']}"
            elif "street" in res and "houseNumber" in res:
                home.address = f"{res['street']} {res['houseNumber']}"

            # Price is sometimes whole euros, sometimes not. But is always in period instead of comma
            # Use default python float to int rounding method
            home.price = int(float(res['netRent']))

            # Since the customers of this platform can have different subdomains, paths etc..
            # We have to map the corporation to a full path where the listing is accessible
            map = {
                'antares': 'https://wonen.thuisbijantares.nl/aanbod/nu-te-huur/te-huur/details/',
                'dewoningzoeker': 'https://www.dewoningzoeker.nl/aanbod/te-huur/details/',
                'frieslandhuurt': 'https://www.frieslandhuurt.nl/aanbod/nu-te-huur/huurwoningen/details/',
                'hollandrijnland': 'https://www.hureninhollandrijnland.nl/aanbod/nu-te-huur/huurwoningen/details/',
                'hwwonen': 'https://www.thuisbijhwwonen.nl/aanbod/nu-te-huur/huurwoningen/details/',
                'klikvoorwonen': 'https://www.klikvoorwonen.nl/aanbod/nu-te-huur/huurwoningen/details/',
                'mercatus-aanbod': 'https://woningaanbod.mercatus.nl/aanbod/te-huur/details/',
                'mosaic-plaza': 'https://plaza.newnewnew.space/aanbod/huurwoningen/details/',
                'noordveluwe': 'https://www.hurennoordveluwe.nl/aanbod/nu-te-huur/huurwoningen/details/',
                'oostwestwonen': 'https://woningzoeken.oostwestwonen.nl/aanbod/nu-te-huur/huurwoningen/details/',
                'studentenenschede': 'https://www.roomspot.nl/aanbod/te-huur/details/',
                'svnk': 'https://www.svnk.nl/aanbod/nu-te-huur/huurwoningen/details/',
                'thuisindeachterhoek': 'https://www.thuisindeachterhoek.nl/aanbod/te-huur/details/',
                'thuisinlimburg': 'https://www.thuisinlimburg.nl/aanbod/nu-te-huur/huurwoningen/details/',
                'thuiskompas': 'https://www.thuiskompas.nl/aanbod/nu-te-huur/te-huur/details/',
                'thuispoort': 'https://www.thuispoort.nl/aanbod/te-huur/details/',
                'thuispoortstudenten': 'https://www.thuispoortstudentenwoningen.nl/aanbod/details/',
                'woninghuren': 'https://www.woninghuren.nl/aanbod/te-huur/details/',
                'woninginzicht': 'https://www.woninginzicht.nl/aanbod/te-huur/details/',
                'wooniezie': 'https://www.wooniezie.nl/aanbod/nu-te-huur/te-huur/details/',
                'woonkeusstedendriehoek': 'https://www.woonkeus-stedendriehoek.nl/aanbod/nu-te-huur/huurwoningen/details/',
                'woonnethaaglanden': 'https://www.woonnet-haaglanden.nl/aanbod/nu-te-huur/te-huur/details/',
                'woontij': 'https://www.wonenindekop.nl/aanbod/nu-te-huur/huurwoningen/details/',
                'zuidwestwonen': 'https://www.zuidwestwonen.nl/aanbod/nu-te-huur/huurwoningen/details/'
            }
            home.url = f"{map[corp]}{res['urlKey']}"

            self.homes.append(home)

    def parse_woonnet_rijnmond(self, r: requests.models.Response):
        results = json.loads(r.content)['d']['aanbod']
        for res in results:
            # Only include livable spaces, this excludes parking lots, buildings as a whole etc...
            if not res['gebruik'] == 'Woning':
                continue

            home = Home(agency="woonnet_rijnmond")

            if res['huisletter']:
                home.address = f"{res['straat']} {res['huisnummer']} {res['huisletter']}"
            elif res['huisnummertoevoeging']:  # Probably not needed, only seen in complex buildings
                home.address = f"{res['straat']} {res['huisnummer']} {res['huisnummertoevoeging']}"
            else:
                home.address = f"{res['straat']} {res['huisnummer']}"

            home.city = res["plaats"]
            home.url = f"https://www.woonnetrijnmond.nl/detail/{res['id']}"
            home.price = int(float(res['kalehuur'].replace(",", ".")))  # float before int because of rounding
            self.homes.append(home)
        
    def parse_woonin(self, r: requests.models.Response):
        results = json.loads(r.content)['objects']
        for res in results:
            # Woonin includes houses which are already rented, we only want the empty houses!
            if res["type"] == "huur" and not res.get("verhuurd", False):
                home = Home(agency="woonin")
                home.address = res["straat"]
                home.city = res["plaats"]
                home.url = f"https://ik-zoek.woonin.nl{res['url']}"  # Given URL links directly to listing
                home.price = int(res["vraagPrijs"][2:].replace(".", ""))  # Remove dot and skip currency+space prefix
                self.homes.append(home)
    
    def parse_vesteda(self, r: requests.models.Response):
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
        
    def parse_vbt(self, r: requests.models.Response):
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
            
    def parse_alliantie(self, r: requests.models.Response):
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
            
    def parse_woningnet_dak(self, r: requests.models.Response, regio: str):
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
            
    def parse_bouwinvest(self, r: requests.models.Response):
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
    
    def parse_krk(self, r: requests.models.Response):
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
            
    def parse_pararius(self, r: requests.models.Response):
        results = BeautifulSoup(r.content, "html.parser").find_all("section", class_="listing-search-item--for-rent")
        
        for res in results:
            home = Home(agency="pararius")
        
            # Check if the listing contains all the required information
            address_item = res.find("a", class_="listing-search-item__link--title")
            city_item = res.find("div", class_="listing-search-item__sub-title")
            url_item = res.find("a", class_="listing-search-item__link--title")
            price_item = res.find("div", class_="listing-search-item__price")
            if not address_item or not city_item or not url_item or not price_item:
                address_item, city_item, url_item, price_item = None, None, None, None
                continue
        
            # A lot of properties on Pararius don't include house numbers, so it's impossible to keep track of them because
            # right now homes are tracked by address, not by URL (which has its own downsides).
            # This is probably not 100% reliable either, but it's close enough.
            address = str(address_item.contents[0]).strip()
            if not re.search("[0-9]", address):
                continue
            if re.search("^[0-9]", address):  # Filter "1e Foobarstraat", etc.
                continue
                
            home.address = ' '.join(address.split(' ')[1:])  # All items start with one of ["Appartement", "Huis", "Studio", "Kamer"]
            city = str(city_item.contents[0]).strip()
            home.city = ' '.join(city.split(' ')[2:]).split('(')[0].strip()  # Don't ask
            home.url = "https://pararius.nl" + str(url_item["href"])
            price = str(price_item.contents[0]).strip().replace('\xa0', '')
            
            # If unable to cast to int, the price is not available so skip the listing
            try:
                home.price = int(price[1:].split(' ')[0].replace('.', ''))
            except:
                continue
            
            self.homes.append(home)
            
    def parse_funda(self, r: requests.models.Response):
        results = json.loads(r.content)["responses"][0]["hits"]["hits"]
        
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
    def parse_rebo(self, r: requests.models.Response):
        results = json.loads(r.content)["hits"]
        for res in results:
            home = Home(agency="rebo")
            home.address = res["address"]
            home.city = res["city"]
            home.url = "https://www.rebogroep.nl/nl/aanbod/" + res["slug"]
            home.price = int(res["price"])
            self.homes.append(home)

    def parse_nmg(self, r: requests.models.Response):
        results = BeautifulSoup(r.content, "html.parser").find_all("article", class_="house huur")
        for res in results:
            home = Home(agency="nmg")
            content = res.find_all("div", class_="house__content")[0]
            if address_tag := content.select_one('.house__heading h2'):
                home.address = address_tag.text.strip().split('\t\t\t\t')[0]
            if city_tag := content.select_one('.house__heading h2 span'):
                home.city = city_tag.text.strip()
            if url_tag := res.select_one('.house__overlay'):
                home.url = str(url_tag["href"])
            # Remove all non-numeric characters from the price
            if price_tag := res.select_one('.house__list-item .house__icon--value + span'):
                rawprice = price_tag.text.strip()
                home.price = int(re.sub(r'\D', '', rawprice))
            if (home.address and home.city and home.url and home.price):
                self.homes.append(home)

    def parse_vbo(self, r: requests.models.Response):
        results = BeautifulSoup(r.content, "html.parser").find_all("a", class_="propertyLink")
        for res in results:
            home = Home(agency="vbo")
            home.url = str(res["href"])
            if address_tag := res.select_one(".street"):
                home.address = address_tag.text.strip()
            if city_tag := res.select_one(".city"):
                home.city = city_tag.text.strip()
            if price_tag := res.select_one(".price"):
                rawprice = price_tag.text
                end = rawprice.index(",") # Every price is terminated with a trailing ,
                home.price = int(rawprice[2:end].replace(".", ""))
            if (home.address and home.city and home.url and home.price):
                self.homes.append(home)

    def parse_atta(self, r: requests.models.Response):
        results = BeautifulSoup(r.content, "html.parser").find_all("div", class_="list__object")
        for res in results:
            home = Home(agency="atta")
            if url_tag := res.select_one("a"):
                home.url = str(url_tag["href"])
            if address_tag := res.select_one(".object-list__address"):
                home.address = address_tag.text
            if city_tag := res.select_one(".object-list__city"):
                home.city = city_tag.text.strip()
            if price_tag := res.select_one(".object-list__price"):
                home.price = int(price_tag.text[2:].replace(".", ""))
            if (home.address and home.city and home.url and home.price):
                self.homes.append(home)

    def parse_ooms(self, r: requests.models.Response):
        results = json.loads(r.content)["objects"]
        rentals = filter(lambda res: res["filters"]["buy_rent"] == "rent", results)
        for res in rentals:
            home = Home(agency="ooms")
            home.url = f"https://ooms.com/wonen/aanbod/{res['slug']}"

            addition = res.get("house_number_addition")
            # Explicitly check for None because it can be {"house_number_addition": None}
            # in which case using a default value in `get` would not work
            if addition == None:
                addition = ""

            home.address = f"{res['street_name']} {res['house_number']} {addition}"
            home.city = res["place"]
            home.price = res["rent_price"]
            self.homes.append(home)

    def parse_woonmatchwaterland(self, r: requests.models.Response):
        soup = BeautifulSoup(r.content, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__", type="application/json")
        if script is not None and script.string:
            # Convert the JSON text to a Python object
            results = json.loads(script.string)["props"]["pageProps"]["houses"]
            if results:
                for res in results:
                    home = Home(agency="woonmatchwaterland")
                    home.address = res["address"]["street"] + " " + str(res["address"]["number"])
                    home.city = res["address"]["city"]
                    home.url = "https://woonmatchwaterland.nl/houses/" + res["advert"]
                    home.price = int(float(res["details"]["grossrent"]))
                    self.homes.append(home)

    def parse_entree(self, r: requests.models.Response):
        results = json.loads(r.content)["d"]["aanbod"]
        for res in results:
            skip_prop = ["Garage", "Parkeerplaats"]
            home = Home(agency="entree")
            if res["objecttype"] not in skip_prop:
                if res["huisletter"]:
                    home.address = f"{res['straat']} {res['huisnummer']}"
                else:
                    home.address = f"{res['straat']} {res['huisnummer']}{res['huisletter']}"
                home.city = res["plaats"]
                home.price = int(float(res["kalehuur"].replace(',', '.')))
                home.url = f"https://entree.nu/detail/{res['id']}"
                self.homes.append(home)

    """
    Woonzeker Rentals has a really weird structure. They load all the data
    in a JSON object on page load and then afterwards fill in the rest of the HTML
    with that data.
    """
    def parse_woonzeker(self, r: requests.models.Response):
         scripts = BeautifulSoup(r.content, "html.parser").find_all("script")
         data = str(scripts[3]) # The third script tag has what we need
         needle = "rent:[" # We care about the value of the 'rent' attribute
         start = data.find(needle) + len(needle) - 1
         end = data.find(",configuration") # configuration is the next attribute
         results = chompjs.parse_js_object(data[start:end])

         # Now, we need to get all the possible variables
         func_needle = 'window.__NUXT__=(function('
         func_start = data.find(func_needle)
         func_end = data.find(')', func_start)
         func_args = data[func_start + len(func_needle):func_end].split(",")
         param_needle = '}('
         param_start = data.find(param_needle)
         param_end = data.find('));', param_start)
         params = next(csv.reader([data[param_start + len(param_needle):param_end]], skipinitialspace=True)) # Use csv reader to allow for commas in strings.

         mapping = {}
         for i in range(0, min(len(func_args), len(params))):
             mapping[func_args[i]] = params[i]

         def mapping_or_raw(s: str):
             if s in mapping:
                 return mapping[s]
             else:
                 return s
         for res in results:
             home = Home(agency="woonzeker")

             if (mapping_or_raw(res['mappedStatus']).lower() == "onder optie"):
                 continue # This house is already gone

             address = res['address']
             slug = res['slug']
             extract_regex = re.compile(r"(.*)-([0-9]+)(-([a-zA-Z0-9]+))?") # See discussion in #48 for why we need this
             matches = extract_regex.match(slug)
             if not matches:
                 logging.warning("Unable to pattern match woonzeker slug: {}", slug)
                 continue
             ext = matches.group(4) 
             if ext:
                 if ext.lower() == address['houseNumberExtension'].lower() or address['houseNumberExtension'] not in mapping:
                     ext = address['houseNumberExtension']
                 elif address['houseNumberExtension'] in mapping:
                     ext = mapping[address['houseNumberExtension']]
                 home.address = f"{mapping_or_raw(address['street'])} {mapping_or_raw(address['houseNumber'])} {ext}".strip()
             else:
                 home.address = f"{mapping_or_raw(address['street'])} {mapping_or_raw(address['houseNumber'])}".strip()
             home.city = mapping_or_raw(address['location'])
             home.url = "https://woonzeker.com/aanbod/" + parse.quote(home.city + "/" + res['slug'])  # slug contains the proper url formatting and is always filled in
             home.price = int(mapping_or_raw(res['handover']['price']))
             self.homes.append(home)


    def parse_123wonen(self, r: requests.models.Response):
        results = json.loads(r.content)['pointers']
        for res in results:
            if res['transaction'] == 'Verhuur':
                home = Home(agency="123wonen")
                home.url = f"https://www.123wonen.nl/{res['detailurl']}"
                if res['address_num_extra']:
                    home.address = f"{res['address']} {res['address_num']}{res['address_num_extra']}"
                else:
                    home.address = f"{res['address']} {res['address_num']}"
                home.city = res['city']
                home.price = int(res['price'])
                self.homes.append(home)

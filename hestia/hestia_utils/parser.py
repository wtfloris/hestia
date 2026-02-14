import re
import csv
import json
import chompjs
import logging
import requests
from urllib import parse
from bs4 import BeautifulSoup, NavigableString


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
        elif source == "roofz":
            self.parse_roofz(raw)
        elif source == "vanderlinden":
            self.parse_vanderlinden(raw)
        elif source == "hoekstra":
            self.parse_hoekstra(raw)
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
                'frieslandhuurt': 'https://www.frieslandhuurt.nl/nu-te-huur/woningen/details/',
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
        results = json.loads(r.content)["data"]["housingPublications"]["nodes"]["edges"]
        for res in results:
            home = Home(agency="woonnet_rijnmond")
            home.address = res["node"]["unit"]["location"]["addressLine1"]
            home.city = res["node"]["unit"]["location"]["addressLine2"]
            home.url = f"https://www.woonnetrijnmond.nl/nl-NL/aanbod/advertentie/{res['node']['unit']['slug']['value']}"
            home.price = int(res["node"]["unit"]["basicRent"]["exact"])
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
            if res["objecttype"] not in skip_prop and res["gebruik"] != "Cluster":
                if res["huisletter"]:
                    home.address = f"{res['straat']} {res['huisnummer']}{res['huisletter']}"
                else:
                    home.address = f"{res['straat']} {res['huisnummer']}"
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

    def parse_roofz(self, r: requests.models.Response):
        soup = BeautifulSoup(r.content, "html.parser")

        # Find the __NUXT__ script containing all page data
        nuxt_data = None
        for script in soup.find_all("script"):
            if script.string and 'window.__NUXT__' in script.string:
                nuxt_data = script.string
                break
        if not nuxt_data:
            return

        # Build variable mapping from the Nuxt IIFE: (function(a,b,...){return {...}}(val1,val2,...))
        func_start = nuxt_data.index('(function(') + len('(function(')
        func_end = nuxt_data.index(')', func_start)
        func_args = nuxt_data[func_start:func_end].split(',')

        param_end = nuxt_data.rfind('))')
        param_start = nuxt_data.rfind('}(', 0, param_end)
        params = next(csv.reader([nuxt_data[param_start + 2:param_end]], skipinitialspace=True))

        mapping = {}
        for i in range(min(len(func_args), len(params))):
            mapping[func_args[i]] = params[i]

        # Find the rent array in the raw JS
        rent_idx = nuxt_data.find('rent:[') + len('rent:')
        bracket_count = 0
        rent_end = rent_idx
        for i, c in enumerate(nuxt_data[rent_idx:]):
            if c == '[':
                bracket_count += 1
            elif c == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    rent_end = rent_idx + i + 1
                    break

        # Substitute unquoted variable references with their resolved values
        # This preserves quoted strings while resolving bare identifiers
        rent_resolved = self._substitute_nuxt_vars(nuxt_data[rent_idx:rent_end], mapping)
        results = chompjs.parse_js_object(rent_resolved)

        for res in results:
            addr = res.get('address', {})
            ho = res.get('handover', {})
            status = str(res.get('status', ''))

            # Filter already-rented and under-option listings
            if any(x in status.lower() for x in ['rented', 'option', 'contract']):
                continue

            street = addr.get('street', '')
            house_num = str(addr.get('houseNumber', ''))
            ext = addr.get('houseNumberExtension', '')
            city = addr.get('location', '')
            price = ho.get('price', 0)
            slug = res.get('slug', '')

            if not street or not house_num or not city or not price:
                continue

            home = Home(agency="roofz")
            home.address = f"{street} {house_num}"
            if ext:
                home.address += f" {ext}"
            home.city = city
            home.url = f"https://roofz.eu/availability/{slug}"
            home.price = int(float(price))
            self.homes.append(home)

    def parse_vanderlinden(self, r: requests.models.Response):
        results = BeautifulSoup(r.content, "html.parser").find_all("div", class_="woninginfo")
        for res in results:
            # Filter "Onder optie" listings (already taken)
            label = res.find("div", class_="fotolabel")
            if label and "onder optie" in label.text.lower():
                continue

            address_tag = res.select_one("strong")
            city_tag = res.select_one("div.text-80.mb-0")
            price_tag = res.select_one("div.mt-2")
            url_tag = res.select_one("a.blocklink")
            if not address_tag or not city_tag or not price_tag or not url_tag:
                continue

            address = address_tag.text.strip()
            # Skip project/complex listings without a house number
            if not any(c.isdigit() for c in address):
                continue

            home = Home(agency="vanderlinden")
            home.address = address
            # City is a direct text node in the div; ignore text from child elements
            # (e.g. <span>Studentenwoning</span>, <span>Beschikbaar /</span>)
            city_text = ''.join(
                child for child in city_tag.children if isinstance(child, NavigableString)
            ).strip()
            home.city = city_text
            home.url = "https://www.vanderlinden.nl" + str(url_tag["href"])
            # Price format: "€ 1.184 per maand" or "€ 1.090 - 1.160" (range, use lowest)
            # Some listings say "Op aanvraag" (on request), skip those
            raw_price = price_tag.text.strip()
            raw_price = raw_price.split("per")[0].strip()  # Remove "per maand"
            raw_price = raw_price.replace("€", "").strip()
            raw_price = raw_price.split("-")[0].strip()  # Take lowest price in range
            try:
                home.price = int(raw_price.replace(".", ""))
            except ValueError:
                continue
            self.homes.append(home)

    def parse_hoekstra(self, r: requests.models.Response):
        soup = BeautifulSoup(r.content, "html.parser")
        seen: set[tuple[str, str]] = set()

        def normalize_space(text: str) -> str:
            return " ".join(text.split()).strip()

        def parse_price(value):
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return int(float(value))
            price = ''.join(ch for ch in str(value) if ch.isdigit())
            if not price:
                return None
            return int(price)

        def is_unavailable(text: str) -> bool:
            lowered = text.lower()
            blocked = [
                "verhuurd",
                "onder optie",
                "onder voorbehoud",
                "niet beschikbaar",
                "withdrawn",
                "rentedwithreservation",
                "gereserveerd",
                "rented",
                "under option",
                "not available",
            ]
            return any(word in lowered for word in blocked)

        def is_available_status(status_text: str, availability_text: str = "") -> bool:
            status_norm = normalize_space(status_text).lower()
            availability_norm = normalize_space(availability_text).lower()
            combined = f"{status_norm} {availability_norm}".strip()
            if not combined:
                return False
            if is_unavailable(combined):
                return False
            allowed = ["beschikbaar", "available", "immediatelly", "direct beschikbaar"]
            return any(word in combined for word in allowed)

        def add_home(address: str, city: str, url: str, price, status_text: str = ""):
            address = normalize_space(address or "")
            city = normalize_space(city or "")
            url = normalize_space(url or "")
            parsed_price = parse_price(price)
            if not address or not city or not url or not parsed_price:
                return
            # Project/complex listings without a house number are not trackable.
            if not any(c.isdigit() for c in address):
                return
            if is_unavailable(status_text):
                return

            key = (address.lower(), city.lower())
            if key in seen:
                return
            seen.add(key)

            home = Home(agency="hoekstra")
            home.address = address
            home.city = city
            home.url = parse.urljoin("https://verhuur.makelaardijhoekstra.nl/", url)
            home.price = parsed_price
            self.homes.append(home)

        def parse_ld_node(node):
            if not isinstance(node, dict):
                return

            if "itemListElement" in node and isinstance(node["itemListElement"], list):
                for item in node["itemListElement"]:
                    child = item.get("item", item) if isinstance(item, dict) else item
                    parse_ld_node(child)
                return

            address_data = node.get("address", {})
            if isinstance(address_data, list):
                address_data = address_data[0] if address_data else {}
            if not isinstance(address_data, dict):
                address_data = {}

            offers = node.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if not isinstance(offers, dict):
                offers = {}

            street = address_data.get("streetAddress", "")
            city = address_data.get("addressLocality", "") or node.get("addressLocality", "")
            url = node.get("url") or offers.get("url")
            price = (
                offers.get("price")
                or (offers.get("priceSpecification", {}) if isinstance(offers.get("priceSpecification"), dict) else {}).get("price")
                or node.get("price")
            )
            status_text = " ".join(
                [
                    str(node.get("availability", "")),
                    str(offers.get("availability", "")),
                    str(node.get("description", "")),
                    str(node.get("name", "")),
                ]
            )

            if not street and isinstance(node.get("name"), str):
                name = normalize_space(node["name"])
                if "," in name:
                    street, maybe_city = [part.strip() for part in name.split(",", 1)]
                    if not city:
                        city = maybe_city
                else:
                    street = name

            add_home(street, city, url, price, status_text)

        # Primary path: Hoekstra JSON API payload (`/api/pim`, `/api/search`, etc.).
        # The raw HTML page itself does not include listing data server-side.
        try:
            parsed_json = json.loads(r.content)
            if isinstance(parsed_json, dict):
                api_items = parsed_json.get("items")
                if not isinstance(api_items, list):
                    api_items = parsed_json.get("data")
                if not isinstance(api_items, list):
                    api_items = []
            elif isinstance(parsed_json, list):
                api_items = parsed_json
            else:
                api_items = []

            for item in api_items:
                if not isinstance(item, dict):
                    continue

                status = normalize_space(str(item.get("status", "")))
                availability = ""
                if isinstance(item.get("availability"), dict):
                    availability = str(item["availability"].get("availability", ""))

                if not is_available_status(status, availability):
                    continue

                street = normalize_space(str(item.get("street", "")))
                house_number = normalize_space(str(item.get("houseNumber", "")))
                house_number_addition = normalize_space(str(item.get("houseNumberAddition", "")))
                city = normalize_space(str(item.get("city", "")))

                address = f"{street} {house_number}".strip()
                if house_number_addition and house_number_addition.lower() != "none":
                    address = f"{address}{house_number_addition}"

                listing_id = item.get("id")
                url = ""
                if listing_id:
                    url = f"https://verhuur.makelaardijhoekstra.nl/property-detail.html?id={listing_id}"

                price = (
                    item.get("rentPrice")
                    or item.get("rentPriceExclVat")
                    or item.get("rentPriceInclVat")
                    or (item.get("pimprices", {}) if isinstance(item.get("pimprices"), dict) else {}).get("pricing", {}).get("rent", [{}])[0].get("priceInclVat")
                )

                add_home(address, city, url, price, status)

            if self.homes:
                return
        except json.JSONDecodeError:
            pass

        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue

            stack = [data]
            while stack:
                node = stack.pop()
                if isinstance(node, dict):
                    parse_ld_node(node)
                    for value in node.values():
                        if isinstance(value, (dict, list)):
                            stack.append(value)
                elif isinstance(node, list):
                    stack.extend(node)

        # HTML fallback for card-based listings when JSON-LD is missing/incomplete.
        if not self.homes:
            card_selectors = [
                "article",
                "li",
                "div.aanbod-item",
                "div.object-item",
                "div.property-item",
                "div.search-result__item",
            ]
            for selector in card_selectors:
                for card in soup.select(selector):
                    card_text = normalize_space(card.get_text(" "))
                    if "€" not in card_text:
                        continue
                    if is_unavailable(card_text):
                        continue

                    link = card.select_one("a[href]")
                    if not link:
                        continue

                    address = ""
                    city = ""
                    for node in card.select(
                        ".address, .object-address, .property-address, [itemprop='streetAddress'], h1, h2, h3"
                    ):
                        candidate = normalize_space(node.get_text(" "))
                        if any(ch.isdigit() for ch in candidate):
                            address = candidate
                            break
                    city_node = card.select_one(".city, .object-city, .property-city, [itemprop='addressLocality']")
                    if city_node:
                        city = normalize_space(city_node.get_text(" "))
                    elif address and "," in address:
                        address, city = [part.strip() for part in address.split(",", 1)]

                    price_match = re.search(r"€\s*([\d\.\,]+)", card_text)
                    if not price_match:
                        continue

                    add_home(address, city, link.get("href", ""), price_match.group(1), card_text)

    @staticmethod
    def _substitute_nuxt_vars(js_text, mapping):
        """Replace unquoted variable references in JS text with their mapped string values.
        Properly skips quoted strings to avoid corrupting literal values."""
        result = []
        i = 0
        n = len(js_text)
        while i < n:
            c = js_text[i]
            if c in ('"', "'"):
                quote = c
                j = i + 1
                while j < n:
                    if js_text[j] == '\\' and j + 1 < n:
                        j += 2
                    elif js_text[j] == quote:
                        j += 1
                        break
                    else:
                        j += 1
                result.append(js_text[i:j])
                i = j
            elif c.isalpha() or c in ('_', '$'):
                j = i + 1
                while j < n and (js_text[j].isalnum() or js_text[j] in ('_', '$')):
                    j += 1
                ident = js_text[i:j]
                if ident in ('true', 'false', 'null', 'undefined'):
                    result.append(ident)
                elif ident in mapping:
                    val = mapping[ident]
                    val = val.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
                    result.append(f'"{val}"')
                else:
                    result.append(ident)
                i = j
            else:
                result.append(c)
                i += 1
        return ''.join(result)

## Hestia

Hestia scrapes real estate websites for new rental listings, and broadcasts the results via Telegram. Check out @hestia_homes_bot on Telegram: https://t.me/hestia_homes_bot

### How to contribute

First of all, thanks! If you want to add a website, you need to write a parser. This takes a bit of detective work to find out how the website can be processed best.

Ideally, if you check the requests from your browsers' inspector window, you see it makes a request to an API endpoint that gives you a clean JSON response with all the data you need. If that's the case, you can have a parser as simple as the REBO parser:

```python
def parse_rebo(self, r: requests.models.Response):
    results = json.loads(r.content)["hits"]
    for res in results:
        home = Home(agency="rebo")
        home.address = res["address"]
        home.city = res["city"]
        home.url = "https://www.rebogroep.nl/nl/aanbod/" + res["slug"]
        home.price = int(res["price"])
        self.homes.append(home)
```

Unfortunately, a lot of websites need parsing of the HTML body in order to get all the info. You can do this with BeautifulSoup, but usually requires some extra parsing like removing spaces and processing a price written as `€900,-` to get an integer. See the VBO parser for example:

```python
def parse_vbo(self, r: requests.models.Response):
    results = BeautifulSoup(r.content, "html.parser").find_all("a", class_="propertyLink")
    for res in results:
        home = Home(agency="vbo")
        home.url = res["href"]
        home.address = res.select_one(".street").text.strip()
        home.city = res.select_one(".city").text.strip()
        rawprice = res.select_one(".price").text
        end = rawprice.index(",")  # Every price is terminated with a trailing ,
        home.price = int(rawprice[2:end].replace(".", ""))
        self.homes.append(home)
```

Some websites list homes that have already been rented out. You can filter them out in this code as well. Check the file `hestia.py`, this contains all the parsers for Hestia. The generic structure is that it takes an unprocessed `Response` object from the Python library `requests` (e.g. from `requests.get(url)`) and fills a `Home` object.

If you wrote a parser and want to submit a PR, please include the following info:

```
Target URL
GET or POST
Headers (optional, in Python dict format)
Request data (only for POST, in Python dict format)
```

I'll take your parser and run it in the dev environment for a few days to see how it performs. Does it process all homes correctly? Does the website modify their HTML structure every other day? Does the API endpoint need an updated ID every two weeks (looking at you, Woningnet...)?

### Additional contributors (thanks!):
* [BLOKKADE](https://github.com/BLOKKADE) - NMG Wonen parser
* [Rafaeltheraven](https://github.com/Rafaeltheraven) - VBO and Woonzeker parsers
* [OmriSteiner](https://github.com/OmriSteiner) - Ooms and Atta parsers
* [Ventilaar](https://github.com/ventilaar) - Hexia, Woonnet Rijnmond and Woonin parsers
* [PimMeulensteen](https://github.com/PimMeulensteen) - Woonmatchwaterland parser
* [fernandez-a](https://github.com/fernandez-a) - 123Wonen parser
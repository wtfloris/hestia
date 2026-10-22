"""One malformed listing must be skipped without dropping the rest of the response."""
import json

import pytest

from hestia_utils.parser import HomeResults


def _next_data_html(houses):
    data = {"props": {"pageProps": {"houses": houses}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


def _vesteda(price):
    return {"status": 1, "onlySixtyFivePlus": False, "street": "Kerkstraat", "houseNumber": "10",
            "houseNumberAddition": None, "city": "Amsterdam", "url": "/huurwoning/a", "priceUnformatted": price}


def _vbt(price):
    return {"isBouwinvest": False, "address": {"house": "Kerkstraat 1", "city": "Utrecht"},
            "source": {"externalLink": "https://example.com/1"}, "prices": {"rental": {"price": price}}}


def _alliantie(price):
    return {"isInSelection": True, "address": "Dorpsstraat 5", "url": "huren/amsterdam/dorpsstraat-5", "price": price}


def _krk(price):
    return {"buy_or_rent": "rent", "availability_status": "Beschikbaar", "short_title": "Havenstraat 5",
            "place": "Rotterdam", "url": "https://krk.nl/h5", "rent_price": price}


def _woningnet(price):
    return {"PublicatieLabel": "Appartement", "Id": "p1",
            "Adres": {"Straatnaam": "Dorpsweg", "Huisnummer": "12", "HuisnummerToevoeging": "", "Woonplaats": "Zaandam"},
            "Eenheid": {"Brutohuur": price}}


def _hexia(rent):
    return {"rentBuy": "Huur", "city": {"name": "Leiden"}, "street": "Breestraat", "houseNumber": "15",
            "netRent": rent, "urlKey": "breestraat-15"}


def _woonmatch(rent):
    return {"address": {"street": "Hoofdstraat", "number": 10, "city": "Purmerend"}, "advert": "a1",
            "details": {"grossrent": rent}}


def _rijnmond(rent):
    return {"node": {"unit": {"location": {"addressLine1": "Wijnhaven 20", "addressLine2": "Rotterdam"},
                              "slug": {"value": "wijnhaven-20"}, "basicRent": rent}}}


def _funda(street):
    address = {"house_number": "100", "city": "Amsterdam"}
    if street:
        address["street_name"] = street
    return {"_source": {"address": address, "price": {"rent_price": [2500]},
                        "object_detail_page_relative_url": "/huur/amsterdam/h-100"}}


def _nmg(price):
    return f"""<article class="house huur"><a class="house__overlay" href="https://nmg.nl/1"></a>
        <div class="house__content"><div class="house__heading"><h2>Dorpsstraat 5\t\t\t\t<span>Leiden</span></h2></div></div>
        <div class="house__list-item"><span class="house__icon--value"></span><span>{price}</span></div></article>"""


def _vbo(price):
    return f"""<a class="propertyLink" href="https://vbo.nl/1"><span class="street">Marktplein 3</span>
        <span class="city">Gouda</span><span class="price">{price}</span></a>"""


def _atta(price):
    return f"""<div class="list__object"><a href="https://atta.nl/1"></a>
        <div class="object-list__address">Stationsstraat 8</div><div class="object-list__city">Haarlem</div>
        <div class="object-list__price">{price}</div></div>"""


def _ooms(street):
    res = {"filters": {"buy_rent": "rent"}, "slug": "s", "house_number": "10", "place": "Den Haag", "rent_price": 1400}
    if street:
        res["street_name"] = street
    return res


def _entree(rent):
    return {"objecttype": "Woning", "gebruik": "Wonen", "straat": "Kerkplein", "huisnummer": "5", "huisletter": "",
            "plaats": "Amersfoort", "kalehuur": rent, "id": "e1"}


def _123wonen(price):
    return {"transaction": "Verhuur", "detailurl": "woning/k10", "address": "Kerkstraat", "address_num": "10",
            "address_num_extra": "", "city": "Amsterdam", "price": price}


def _roofz(living_area):
    return {"status": {"code": "available"}, "stage": "available", "slug": "k10",
            "address": {"street": "Kerkstraat", "house_number": "10", "location": "Amsterdam"},
            "handover": {"price": 1500}, "characteristic": {"living_area": living_area}}


def _woonstad(with_url):
    res = {"name": "Kogelvangerstraat 100", "typeLabel": "Vrijesectorhuur", "rentInfo": {"price": 1569.0},
           "state": {"name": "Beschikbaar"},
           "unit": {"address": {"street": "Kogelvangerstraat", "number": 100, "houseletter": "", "addition": "",
                                "city": "ROTTERDAM"}}}
    if with_url:
        res["webSettings"] = {"url": "k-100"}
    return res


def _easylease(addition):
    return {"data": {"label": "Nieuw", "price": 595, "surface": 20,
                     "locality": {"street": "Graafseweg", "city": "Den Bosch", "number": "26", "addition": addition}},
            "page_item_url": "g-26"}


def _roofz_response(mock_response, listings):
    payload = {"data": listings, "meta": {"last_page": 1}}
    r = mock_response(payload)
    r.json.return_value = payload
    r.url = "https://roofz.eu/api/ms/listing/properties"
    return r


# source, wrap(listings) -> response content, good listing, bad listing
CASES = [
    ("vesteda", lambda l: {"results": {"objects": l}}, _vesteda(1500), _vesteda(None)),
    ("vbt", lambda l: {"houses": l}, _vbt(1300), _vbt(None)),
    ("alliantie", lambda l: {"data": l}, _alliantie("€ 1.200"), _alliantie("Op aanvraag")),
    ("krk", lambda l: {"objects": l}, _krk(1100), _krk(None)),
    ("woningnet_dak", lambda l: {"data": {"PublicatieLijst": {"List": l}}}, _woningnet("950.50"), _woningnet(None)),
    ("hexia_hollandrijnland", lambda l: {"data": l}, _hexia("1250.00"), _hexia(None)),
    ("woonmatchwaterland", _next_data_html, _woonmatch("1050.00"), _woonmatch(None)),
    ("woonnet_rijnmond", lambda l: {"data": {"housingPublications": {"nodes": {"edges": l}}}},
     _rijnmond({"exact": 1350}), _rijnmond(None)),
    ("funda", lambda l: {"responses": [{"hits": {"hits": l}}]}, _funda("Herengracht"), _funda(None)),
    ("nmg", lambda l: "<html>" + "".join(l) + "</html>", _nmg("€ 1.100"), _nmg("Prijs op aanvraag")),
    ("vbo", lambda l: "<html>" + "".join(l) + "</html>", _vbo("€ 950,- p/m"), _vbo("€ 950 p/m")),
    ("atta", lambda l: "<html>" + "".join(l) + "</html>", _atta("€ 1.350"), _atta("Op aanvraag")),
    ("ooms", lambda l: {"objects": l}, _ooms("Laan"), _ooms(None)),
    ("entree", lambda l: {"d": {"aanbod": l}}, _entree("985,50"), _entree(None)),
    ("123wonen", lambda l: {"pointers": l}, _123wonen(1600), _123wonen("1250.00")),
    ("roofz", None, _roofz(75), _roofz("45.5")),
    ("woonstadrotterdam", lambda l: {"items": l}, _woonstad(True), _woonstad(False)),
    ("easylease", lambda l: {"values": l}, _easylease(""), _easylease(None)),
]


def _response(mock_response, source, wrap, listings):
    if source == "roofz":
        return _roofz_response(mock_response, listings)
    return mock_response(wrap(listings))


@pytest.mark.parametrize("source,wrap,good,bad", CASES, ids=[c[0] for c in CASES])
def test_bad_listing_is_skipped(mock_response, source, wrap, good, bad):
    results = HomeResults(source, _response(mock_response, source, wrap, [bad, good]))
    assert len(results.homes) == 1


@pytest.mark.parametrize("source,wrap,good,bad", CASES, ids=[c[0] for c in CASES])
def test_all_listings_bad_raises(mock_response, source, wrap, good, bad):
    with pytest.raises(ValueError, match="malformed"):
        HomeResults(source, _response(mock_response, source, wrap, [bad]))

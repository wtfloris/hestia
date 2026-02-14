import json
import pytest
from hestia_utils.parser import Home, HomeResults


class TestHomeResultsUnknownSource:
    def test_unknown_source_raises(self, mock_response):
        r = mock_response({"data": []})
        with pytest.raises(ValueError, match="Unknown source"):
            HomeResults("nonexistent_agency", r)


class TestHomeResultsIndexing:
    def test_getitem(self, mock_response):
        data = {"hits": [
            {"address": "Straat 1", "city": "Amsterdam", "slug": "straat-1", "price": 1000},
        ]}
        r = mock_response(data)
        results = HomeResults("rebo", r)
        assert results[0].address == "Straat 1"


class TestParseVesteda:
    def test_basic_parsing(self, mock_response):
        data = {"results": {"objects": [
            {
                "status": 1, "onlySixtyFivePlus": False,
                "street": "Kerkstraat", "houseNumber": "10", "houseNumberAddition": None,
                "city": "Amsterdam", "url": "/huurwoning/amsterdam/kerkstraat-10",
                "priceUnformatted": 1500
            }
        ]}}
        r = mock_response(data)
        results = HomeResults("vesteda", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkstraat 10"
        assert results[0].city == "Amsterdam"
        assert results[0].url == "https://vesteda.com/huurwoning/amsterdam/kerkstraat-10"
        assert results[0].price == 1500
        assert results[0].agency == "vesteda"

    def test_with_house_number_addition(self, mock_response):
        data = {"results": {"objects": [
            {
                "status": 1, "onlySixtyFivePlus": False,
                "street": "Hoofdweg", "houseNumber": "5", "houseNumberAddition": "A",
                "city": "Rotterdam", "url": "/huurwoning/rotterdam/hoofdweg-5a",
                "priceUnformatted": 1200
            }
        ]}}
        r = mock_response(data)
        results = HomeResults("vesteda", r)
        assert results[0].address == "Hoofdweg 5A"

    def test_filters_non_status_1(self, mock_response):
        data = {"results": {"objects": [
            {
                "status": 0, "onlySixtyFivePlus": False,
                "street": "Straat", "houseNumber": "1", "houseNumberAddition": None,
                "city": "Amsterdam", "url": "/a", "priceUnformatted": 1000
            },
            {
                "status": 2, "onlySixtyFivePlus": False,
                "street": "Straat", "houseNumber": "2", "houseNumberAddition": None,
                "city": "Amsterdam", "url": "/b", "priceUnformatted": 1000
            }
        ]}}
        r = mock_response(data)
        results = HomeResults("vesteda", r)
        assert len(results.homes) == 0

    def test_filters_sixty_five_plus(self, mock_response):
        data = {"results": {"objects": [
            {
                "status": 1, "onlySixtyFivePlus": True,
                "street": "Straat", "houseNumber": "1", "houseNumberAddition": None,
                "city": "Amsterdam", "url": "/a", "priceUnformatted": 1000
            }
        ]}}
        r = mock_response(data)
        results = HomeResults("vesteda", r)
        assert len(results.homes) == 0

    def test_empty_results(self, mock_response):
        data = {"results": {"objects": []}}
        r = mock_response(data)
        results = HomeResults("vesteda", r)
        assert len(results.homes) == 0


class TestParseVbt:
    def test_basic_parsing(self, mock_response):
        data = {"houses": [
            {
                "isBouwinvest": False,
                "address": {"house": "Kerkstraat 1", "city": "Utrecht"},
                "source": {"externalLink": "https://example.com/1"},
                "prices": {"rental": {"price": 1300}}
            }
        ]}
        r = mock_response(data)
        results = HomeResults("vbt", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkstraat 1"
        assert results[0].city == "Utrecht"
        assert results[0].price == 1300
        assert results[0].agency == "vbt"

    def test_filters_bouwinvest(self, mock_response):
        data = {"houses": [
            {
                "isBouwinvest": True,
                "address": {"house": "Straat 1", "city": "Amsterdam"},
                "source": {"externalLink": "https://example.com/1"},
                "prices": {"rental": {"price": 1000}}
            }
        ]}
        r = mock_response(data)
        results = HomeResults("vbt", r)
        assert len(results.homes) == 0


class TestParseAlliantie:
    def test_basic_parsing(self, mock_response):
        data = {"data": [
            {
                "isInSelection": True,
                "address": "Dorpsstraat 5",
                "url": "huren/amsterdam/dorpsstraat-5-abc123",
                "price": "€ 1.200"
            }
        ]}
        r = mock_response(data)
        results = HomeResults("alliantie", r)
        assert len(results.homes) == 1
        assert results[0].address == "Dorpsstraat 5"
        assert results[0].city == "Amsterdam"
        assert results[0].url == "https://ik-zoek.de-alliantie.nl/huren/amsterdam/dorpsstraat-5-abc123"
        assert results[0].price == 1200

    def test_filters_not_in_selection(self, mock_response):
        data = {"data": [
            {
                "isInSelection": False,
                "address": "Straat 1",
                "url": "huren/amsterdam/straat-1-abc",
                "price": "€ 1.000"
            }
        ]}
        r = mock_response(data)
        results = HomeResults("alliantie", r)
        assert len(results.homes) == 0


class TestParseBouwinvest:
    def test_basic_parsing(self, mock_response):
        data = {"data": [
            {
                "class": "Unit",
                "name": "Keizersgracht 100",
                "address": {"city": "Amsterdam"},
                "url": "https://bouwinvest.nl/1",
                "price": {"price": 2000}
            }
        ]}
        r = mock_response(data)
        results = HomeResults("bouwinvest", r)
        assert len(results.homes) == 1
        assert results[0].address == "Keizersgracht 100"
        assert results[0].price == 2000

    def test_filters_project_class(self, mock_response):
        data = {"data": [
            {
                "class": "Project",
                "name": "Nieuwbouwproject",
                "address": {"city": "Amsterdam"},
                "url": "https://bouwinvest.nl/2",
                "price": {"price": 1500}
            }
        ]}
        r = mock_response(data)
        results = HomeResults("bouwinvest", r)
        assert len(results.homes) == 0


class TestParseKrk:
    def test_basic_parsing(self, mock_response):
        data = {"objects": [
            {
                "buy_or_rent": "rent",
                "availability_status": "Beschikbaar",
                "short_title": "Havenstraat 5",
                "place": "Rotterdam",
                "url": "https://krk.nl/havenstraat-5",
                "rent_price": 1100
            }
        ]}
        r = mock_response(data)
        results = HomeResults("krk", r)
        assert len(results.homes) == 1
        assert results[0].address == "Havenstraat 5"
        assert results[0].price == 1100

    def test_filters_non_rent(self, mock_response):
        data = {"objects": [
            {
                "buy_or_rent": "buy",
                "availability_status": "Beschikbaar",
                "short_title": "Straat 1", "place": "Amsterdam",
                "url": "https://krk.nl/1", "rent_price": 500
            }
        ]}
        r = mock_response(data)
        results = HomeResults("krk", r)
        assert len(results.homes) == 0

    def test_filters_unavailable(self, mock_response):
        data = {"objects": [
            {
                "buy_or_rent": "rent",
                "availability_status": "Verhuurd",
                "short_title": "Straat 1", "place": "Amsterdam",
                "url": "https://krk.nl/1", "rent_price": 500
            }
        ]}
        r = mock_response(data)
        results = HomeResults("krk", r)
        assert len(results.homes) == 0


class TestParseWoningnetDak:
    def test_basic_parsing(self, mock_response):
        data = {"data": {"PublicatieLijst": {"List": [
            {
                "PublicatieLabel": "Eengezinswoning",
                "Adres": {
                    "Straatnaam": "Dorpsweg",
                    "Huisnummer": "12",
                    "HuisnummerToevoeging": "",
                    "Woonplaats": "Zaandam"
                },
                "Eenheid": {"Brutohuur": "950.50"},
                "Id": "pub123"
            }
        ]}}}
        r = mock_response(data)
        results = HomeResults("woningnet_dak", r)
        assert len(results.homes) == 1
        assert results[0].address == "Dorpsweg 12"
        assert results[0].city == "Zaandam"
        assert results[0].price == 950
        assert results[0].agency == "woningnet_dak"
        assert "dak.mijndak.nl" in results[0].url

    def test_with_house_number_addition(self, mock_response):
        data = {"data": {"PublicatieLijst": {"List": [
            {
                "PublicatieLabel": "Appartement",
                "Adres": {
                    "Straatnaam": "Dorpsweg",
                    "Huisnummer": "12",
                    "HuisnummerToevoeging": "B",
                    "Woonplaats": "Zaandam"
                },
                "Eenheid": {"Brutohuur": "800.0"},
                "Id": "pub456"
            }
        ]}}}
        r = mock_response(data)
        results = HomeResults("woningnet_dak", r)
        assert results[0].address == "Dorpsweg 12 B"

    def test_filters_seniorenwoning(self, mock_response):
        data = {"data": {"PublicatieLijst": {"List": [
            {
                "PublicatieLabel": "Seniorenwoning",
                "Adres": {"Straatnaam": "S", "Huisnummer": "1", "HuisnummerToevoeging": "", "Woonplaats": "Z"},
                "Eenheid": {"Brutohuur": "800.0"},
                "Id": "1"
            }
        ]}}}
        r = mock_response(data)
        results = HomeResults("woningnet_dak", r)
        assert len(results.homes) == 0

    def test_filters_zero_price(self, mock_response):
        data = {"data": {"PublicatieLijst": {"List": [
            {
                "PublicatieLabel": "Woning",
                "Adres": {"Straatnaam": "S", "Huisnummer": "1", "HuisnummerToevoeging": "", "Woonplaats": "Z"},
                "Eenheid": {"Brutohuur": "0.0"},
                "Id": "1"
            }
        ]}}}
        r = mock_response(data)
        results = HomeResults("woningnet_dak", r)
        assert len(results.homes) == 0


class TestParseHexia:
    def test_basic_parsing(self, mock_response):
        data = {"data": [
            {
                "rentBuy": "Huur",
                "city": {"name": "Leiden"},
                "street": "Breestraat",
                "houseNumber": "15",
                "houseNumberAddition": None,
                "netRent": "1250.00",
                "urlKey": "breestraat-15"
            }
        ]}
        r = mock_response(data)
        results = HomeResults("hexia_hollandrijnland", r)
        assert len(results.homes) == 1
        assert results[0].address == "Breestraat 15"
        assert results[0].city == "Leiden"
        assert results[0].price == 1250
        assert results[0].agency == "hexia_hollandrijnland"
        assert "hureninhollandrijnland.nl" in results[0].url

    def test_with_house_number_addition(self, mock_response):
        data = {"data": [
            {
                "rentBuy": "Huur",
                "city": {"name": "Leiden"},
                "street": "Breestraat",
                "houseNumber": "15",
                "houseNumberAddition": "B",
                "netRent": "1100",
                "urlKey": "breestraat-15b"
            }
        ]}
        r = mock_response(data)
        results = HomeResults("hexia_hollandrijnland", r)
        assert results[0].address == "Breestraat 15 B"

    def test_filters_non_huur(self, mock_response):
        data = {"data": [
            {
                "rentBuy": "Koop",
                "city": {"name": "Leiden"},
                "street": "Breestraat",
                "houseNumber": "15",
                "houseNumberAddition": None,
                "netRent": "1250",
                "urlKey": "breestraat-15"
            }
        ]}
        r = mock_response(data)
        results = HomeResults("hexia_hollandrijnland", r)
        assert len(results.homes) == 0

    def test_filters_missing_fields(self, mock_response):
        data = {"data": [
            {
                "rentBuy": "Huur",
                "street": "Breestraat",
                "houseNumber": "15",
                "netRent": "1250",
                "urlKey": "breestraat-15"
                # Missing 'city'
            }
        ]}
        r = mock_response(data)
        results = HomeResults("hexia_hollandrijnland", r)
        assert len(results.homes) == 0

    def test_url_mapping_antares(self, mock_response):
        data = {"data": [
            {
                "rentBuy": "Huur",
                "city": {"name": "Venlo"},
                "street": "Markt",
                "houseNumber": "1",
                "houseNumberAddition": None,
                "netRent": "800",
                "urlKey": "markt-1"
            }
        ]}
        r = mock_response(data)
        results = HomeResults("hexia_antares", r)
        assert "thuisbijantares.nl" in results[0].url


class TestParseWoonmatchwaterland:
    def test_basic_parsing(self, mock_response):
        next_data = {
            "props": {"pageProps": {"houses": [
                {
                    "address": {"street": "Hoofdstraat", "number": 10, "city": "Purmerend"},
                    "advert": "abc-123",
                    "details": {"grossrent": "1050.00"}
                }
            ]}}
        }
        html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script></html>'
        r = mock_response(html)
        results = HomeResults("woonmatchwaterland", r)
        assert len(results.homes) == 1
        assert results[0].address == "Hoofdstraat 10"
        assert results[0].city == "Purmerend"
        assert results[0].price == 1050
        assert "woonmatchwaterland.nl/houses/abc-123" in results[0].url

    def test_no_script_tag(self, mock_response):
        html = "<html><body>No data here</body></html>"
        r = mock_response(html)
        results = HomeResults("woonmatchwaterland", r)
        assert len(results.homes) == 0

    def test_empty_houses(self, mock_response):
        next_data = {"props": {"pageProps": {"houses": []}}}
        html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script></html>'
        r = mock_response(html)
        results = HomeResults("woonmatchwaterland", r)
        assert len(results.homes) == 0


class TestParseWoonnetRijnmond:
    def test_basic_parsing(self, mock_response):
        data = {"data": {"housingPublications": {"nodes": {"edges": [
            {
                "node": {
                    "unit": {
                        "location": {"addressLine1": "Wijnhaven 20", "addressLine2": "Rotterdam"},
                        "slug": {"value": "wijnhaven-20"},
                        "basicRent": {"exact": 1350}
                    }
                }
            }
        ]}}}}
        r = mock_response(data)
        results = HomeResults("woonnet_rijnmond", r)
        assert len(results.homes) == 1
        assert results[0].address == "Wijnhaven 20"
        assert results[0].city == "Rotterdam"
        assert results[0].price == 1350
        assert "woonnetrijnmond.nl" in results[0].url

    def test_empty_edges(self, mock_response):
        data = {"data": {"housingPublications": {"nodes": {"edges": []}}}}
        r = mock_response(data)
        results = HomeResults("woonnet_rijnmond", r)
        assert len(results.homes) == 0


class TestParseWoonin:
    def test_basic_parsing(self, mock_response):
        data = {"objects": [
            {
                "type": "huur",
                "verhuurd": False,
                "straat": "Prinsengracht 100",
                "plaats": "Amsterdam",
                "url": "/woning/prinsengracht-100",
                "vraagPrijs": "€ 1.800"
            }
        ]}
        r = mock_response(data)
        results = HomeResults("woonin", r)
        assert len(results.homes) == 1
        assert results[0].address == "Prinsengracht 100"
        assert results[0].city == "Amsterdam"
        assert results[0].price == 1800
        assert "ik-zoek.woonin.nl/woning/prinsengracht-100" in results[0].url

    def test_filters_rented(self, mock_response):
        data = {"objects": [
            {
                "type": "huur",
                "verhuurd": True,
                "straat": "Straat 1", "plaats": "Amsterdam",
                "url": "/1", "vraagPrijs": "€ 1.000"
            }
        ]}
        r = mock_response(data)
        results = HomeResults("woonin", r)
        assert len(results.homes) == 0

    def test_filters_non_huur(self, mock_response):
        data = {"objects": [
            {
                "type": "koop",
                "verhuurd": False,
                "straat": "Straat 1", "plaats": "Amsterdam",
                "url": "/1", "vraagPrijs": "€ 1.000"
            }
        ]}
        r = mock_response(data)
        results = HomeResults("woonin", r)
        assert len(results.homes) == 0


class TestParsePararius:
    def _make_listing_html(self, address="Appartement Kerkstraat 10", city="Te huur Amsterdam",
                           url="/huurwoning/amsterdam/kerkstraat-10", price="\u20ac1.500 /mnd",
                           include_all=True):
        parts = '<section class="listing-search-item--for-rent">'
        if include_all:
            parts += f'<a class="listing-search-item__link--title" href="{url}">{address}</a>'
            parts += f'<div class="listing-search-item__sub-title">{city}</div>'
            parts += f'<div class="listing-search-item__price">{price}</div>'
        parts += '</section>'
        return parts

    def test_basic_parsing(self, mock_response):
        html = f"<html>{self._make_listing_html()}</html>"
        r = mock_response(html)
        results = HomeResults("pararius", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkstraat 10"
        assert results[0].city == "Amsterdam"
        assert results[0].price == 1500

    def test_filters_no_house_number(self, mock_response):
        html = f"<html>{self._make_listing_html(address='Appartement Kerkstraat')}</html>"
        r = mock_response(html)
        results = HomeResults("pararius", r)
        assert len(results.homes) == 0

    def test_filters_address_starting_with_number(self, mock_response):
        """Addresses where the raw content starts with a digit (no type prefix) are filtered."""
        html = f"<html>{self._make_listing_html(address='1e Kerkstraat 5')}</html>"
        r = mock_response(html)
        results = HomeResults("pararius", r)
        assert len(results.homes) == 0

    def test_missing_elements(self, mock_response):
        html = f"<html>{self._make_listing_html(include_all=False)}</html>"
        r = mock_response(html)
        results = HomeResults("pararius", r)
        assert len(results.homes) == 0


class TestParseFunda:
    def test_basic_parsing(self, mock_response):
        data = {"responses": [{"hits": {"hits": [
            {
                "_source": {
                    "address": {
                        "street_name": "Herengracht",
                        "house_number": "100",
                        "city": "Amsterdam"
                    },
                    "price": {"rent_price": [2500]},
                    "object_detail_page_relative_url": "/huur/amsterdam/herengracht-100"
                }
            }
        ]}}]}
        r = mock_response(data)
        results = HomeResults("funda", r)
        assert len(results.homes) == 1
        assert results[0].address == "Herengracht 100"
        assert results[0].city == "Amsterdam"
        assert results[0].price == 2500
        assert "funda.nl" in results[0].url

    def test_with_suffix(self, mock_response):
        data = {"responses": [{"hits": {"hits": [
            {
                "_source": {
                    "address": {
                        "street_name": "Herengracht",
                        "house_number": "100",
                        "house_number_suffix": "A",
                        "city": "Amsterdam"
                    },
                    "price": {"rent_price": [2000]},
                    "object_detail_page_relative_url": "/huur/amsterdam/herengracht-100a"
                }
            }
        ]}}]}
        r = mock_response(data)
        results = HomeResults("funda", r)
        assert results[0].address == "Herengracht 100 A"

    def test_suffix_with_dash(self, mock_response):
        data = {"responses": [{"hits": {"hits": [
            {
                "_source": {
                    "address": {
                        "street_name": "Herengracht",
                        "house_number": "100",
                        "house_number_suffix": "-1",
                        "city": "Amsterdam"
                    },
                    "price": {"rent_price": [2000]},
                    "object_detail_page_relative_url": "/huur/amsterdam/herengracht-100-1"
                }
            }
        ]}}]}
        r = mock_response(data)
        results = HomeResults("funda", r)
        assert results[0].address == "Herengracht 100-1"

    def test_filters_missing_house_number(self, mock_response):
        data = {"responses": [{"hits": {"hits": [
            {
                "_source": {
                    "address": {"street_name": "Project", "city": "Amsterdam"},
                    "price": {"rent_price": [1000]},
                    "object_detail_page_relative_url": "/huur/amsterdam/project"
                }
            }
        ]}}]}
        r = mock_response(data)
        results = HomeResults("funda", r)
        assert len(results.homes) == 0

    def test_filters_missing_rent_price(self, mock_response):
        data = {"responses": [{"hits": {"hits": [
            {
                "_source": {
                    "address": {"street_name": "Straat", "house_number": "1", "city": "Amsterdam"},
                    "price": {},
                    "object_detail_page_relative_url": "/huur/amsterdam/straat-1"
                }
            }
        ]}}]}
        r = mock_response(data)
        results = HomeResults("funda", r)
        assert len(results.homes) == 0


class TestParseRebo:
    def test_basic_parsing(self, mock_response):
        data = {"hits": [
            {
                "address": "Kerkweg 5",
                "city": "Delft",
                "slug": "kerkweg-5-delft",
                "price": 1200
            }
        ]}
        r = mock_response(data)
        results = HomeResults("rebo", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkweg 5"
        assert results[0].city == "Delft"
        assert results[0].price == 1200
        assert "rebogroep.nl" in results[0].url

    def test_empty_hits(self, mock_response):
        data = {"hits": []}
        r = mock_response(data)
        results = HomeResults("rebo", r)
        assert len(results.homes) == 0


class TestParseNmg:
    def test_basic_parsing(self, mock_response):
        html = """<html><article class="house huur">
            <a class="house__overlay" href="https://nmg.nl/woning/1"></a>
            <div class="house__content">
                <div class="house__heading"><h2>Dorpsstraat 5\t\t\t\t<span>Leiden</span></h2></div>
            </div>
            <div class="house__list-item"><span class="house__icon--value"></span><span>€ 1.100</span></div>
        </article></html>"""
        r = mock_response(html)
        results = HomeResults("nmg", r)
        assert len(results.homes) == 1
        assert results[0].address == "Dorpsstraat 5"
        assert results[0].city == "Leiden"
        assert results[0].price == 1100
        assert results[0].url == "https://nmg.nl/woning/1"


class TestParseVbo:
    def test_basic_parsing(self, mock_response):
        html = """<html><a class="propertyLink" href="https://vbo.nl/woning/1">
            <span class="street">Marktplein 3</span>
            <span class="city">Gouda</span>
            <span class="price">€ 950,- p/m</span>
        </a></html>"""
        r = mock_response(html)
        results = HomeResults("vbo", r)
        assert len(results.homes) == 1
        assert results[0].address == "Marktplein 3"
        assert results[0].city == "Gouda"
        assert results[0].price == 950
        assert results[0].url == "https://vbo.nl/woning/1"


class TestParseAtta:
    def test_basic_parsing(self, mock_response):
        html = """<html><div class="list__object">
            <a href="https://atta.nl/woning/1"></a>
            <div class="object-list__address">Stationsstraat 8</div>
            <div class="object-list__city"> Haarlem </div>
            <div class="object-list__price">€ 1.350</div>
        </div></html>"""
        r = mock_response(html)
        results = HomeResults("atta", r)
        assert len(results.homes) == 1
        assert results[0].address == "Stationsstraat 8"
        assert results[0].city == "Haarlem"
        assert results[0].price == 1350


class TestParseOoms:
    def test_basic_parsing(self, mock_response):
        data = {"objects": [
            {
                "filters": {"buy_rent": "rent"},
                "slug": "laan-van-meerdervoort-10",
                "street_name": "Laan van Meerdervoort",
                "house_number": "10",
                "house_number_addition": "A",
                "place": "Den Haag",
                "rent_price": 1400
            }
        ]}
        r = mock_response(data)
        results = HomeResults("ooms", r)
        assert len(results.homes) == 1
        assert results[0].address == "Laan van Meerdervoort 10 A"
        assert results[0].city == "Den Haag"
        assert results[0].price == 1400

    def test_none_addition(self, mock_response):
        data = {"objects": [
            {
                "filters": {"buy_rent": "rent"},
                "slug": "straat-1",
                "street_name": "Straat",
                "house_number": "1",
                "house_number_addition": None,
                "place": "Amsterdam",
                "rent_price": 1000
            }
        ]}
        r = mock_response(data)
        results = HomeResults("ooms", r)
        assert results[0].address == "Straat 1 "

    def test_filters_non_rent(self, mock_response):
        data = {"objects": [
            {
                "filters": {"buy_rent": "buy"},
                "slug": "straat-1",
                "street_name": "Straat",
                "house_number": "1",
                "house_number_addition": None,
                "place": "Amsterdam",
                "rent_price": 0
            }
        ]}
        r = mock_response(data)
        results = HomeResults("ooms", r)
        assert len(results.homes) == 0


class TestParseEntree:
    def test_basic_parsing(self, mock_response):
        data = {"d": {"aanbod": [
            {
                "objecttype": "Woning",
                "gebruik": "Wonen",
                "straat": "Kerkplein",
                "huisnummer": "5",
                "huisletter": "",
                "plaats": "Amersfoort",
                "kalehuur": "985,50",
                "id": "ent123"
            }
        ]}}
        r = mock_response(data)
        results = HomeResults("entree", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkplein 5"
        assert results[0].city == "Amersfoort"
        assert results[0].price == 985
        assert "entree.nu/detail/ent123" in results[0].url

    def test_with_huisletter(self, mock_response):
        data = {"d": {"aanbod": [
            {
                "objecttype": "Woning",
                "gebruik": "Wonen",
                "straat": "Kerkplein",
                "huisnummer": "5",
                "huisletter": "B",
                "plaats": "Amersfoort",
                "kalehuur": "900",
                "id": "ent456"
            }
        ]}}
        r = mock_response(data)
        results = HomeResults("entree", r)
        assert results[0].address == "Kerkplein 5B"

    def test_filters_garage(self, mock_response):
        data = {"d": {"aanbod": [
            {
                "objecttype": "Garage",
                "gebruik": "Wonen",
                "straat": "Straat", "huisnummer": "1", "huisletter": "",
                "plaats": "X", "kalehuur": "100", "id": "1"
            }
        ]}}
        r = mock_response(data)
        results = HomeResults("entree", r)
        assert len(results.homes) == 0

    def test_filters_parkeerplaats(self, mock_response):
        data = {"d": {"aanbod": [
            {
                "objecttype": "Parkeerplaats",
                "gebruik": "Wonen",
                "straat": "Straat", "huisnummer": "1", "huisletter": "",
                "plaats": "X", "kalehuur": "50", "id": "2"
            }
        ]}}
        r = mock_response(data)
        results = HomeResults("entree", r)
        assert len(results.homes) == 0

    def test_filters_cluster(self, mock_response):
        data = {"d": {"aanbod": [
            {
                "objecttype": "Woning",
                "gebruik": "Cluster",
                "straat": "Straat", "huisnummer": "1", "huisletter": "",
                "plaats": "X", "kalehuur": "800", "id": "3"
            }
        ]}}
        r = mock_response(data)
        results = HomeResults("entree", r)
        assert len(results.homes) == 0


class TestParse123wonen:
    def test_basic_parsing(self, mock_response):
        data = {"pointers": [
            {
                "transaction": "Verhuur",
                "detailurl": "woning/kerkstraat-10-amsterdam",
                "address": "Kerkstraat",
                "address_num": "10",
                "address_num_extra": "",
                "city": "Amsterdam",
                "price": 1600
            }
        ]}
        r = mock_response(data)
        results = HomeResults("123wonen", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkstraat 10"
        assert results[0].city == "Amsterdam"
        assert results[0].price == 1600
        assert "123wonen.nl" in results[0].url

    def test_with_num_extra(self, mock_response):
        data = {"pointers": [
            {
                "transaction": "Verhuur",
                "detailurl": "woning/kerkstraat-10a",
                "address": "Kerkstraat",
                "address_num": "10",
                "address_num_extra": "A",
                "city": "Amsterdam",
                "price": 1400
            }
        ]}
        r = mock_response(data)
        results = HomeResults("123wonen", r)
        assert results[0].address == "Kerkstraat 10A"

    def test_filters_non_verhuur(self, mock_response):
        data = {"pointers": [
            {
                "transaction": "Verkoop",
                "detailurl": "woning/straat-1",
                "address": "Straat", "address_num": "1", "address_num_extra": "",
                "city": "Amsterdam", "price": 500000
            }
        ]}
        r = mock_response(data)
        results = HomeResults("123wonen", r)
        assert len(results.homes) == 0


class TestParseWoonzeker:
    def _make_nuxt_html(self, rent_items, mapping=None):
        """Build minimal Nuxt IIFE HTML for woonzeker parser testing."""
        if mapping is None:
            mapping = {}

        # Build function args and params
        func_args = list(mapping.keys()) if mapping else ["a"]
        params = list(mapping.values()) if mapping else ['"unused"']

        func_args_str = ",".join(func_args)
        params_str = ",".join(params)

        rent_js = json.dumps(rent_items)

        script = f"""<script></script>
<script></script>
<script></script>
<script>window.__NUXT__=(function({func_args_str}){{return {{rent:{rent_js},configuration:[]}}}})({params_str}));</script>"""
        return f"<html>{script}</html>"

    def test_basic_parsing(self, mock_response):
        rent_items = [
            {
                "mappedStatus": "available",
                "slug": "kerkstraat-10",
                "address": {
                    "street": "Kerkstraat",
                    "houseNumber": "10",
                    "houseNumberExtension": "",
                    "location": "Breda"
                },
                "handover": {"price": 1100}
            }
        ]
        html = self._make_nuxt_html(rent_items)
        r = mock_response(html)
        results = HomeResults("woonzeker", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkstraat 10"
        assert results[0].city == "Breda"
        assert results[0].price == 1100
        assert "woonzeker.com/aanbod/" in results[0].url

    def test_filters_onder_optie(self, mock_response):
        rent_items = [
            {
                "mappedStatus": "onder optie",
                "slug": "straat-1",
                "address": {
                    "street": "Straat",
                    "houseNumber": "1",
                    "houseNumberExtension": "",
                    "location": "Breda"
                },
                "handover": {"price": 1000}
            }
        ]
        html = self._make_nuxt_html(rent_items)
        r = mock_response(html)
        results = HomeResults("woonzeker", r)
        assert len(results.homes) == 0

    def test_with_extension_in_slug(self, mock_response):
        rent_items = [
            {
                "mappedStatus": "available",
                "slug": "kerkstraat-10-a",
                "address": {
                    "street": "Kerkstraat",
                    "houseNumber": "10",
                    "houseNumberExtension": "A",
                    "location": "Breda"
                },
                "handover": {"price": 1100}
            }
        ]
        html = self._make_nuxt_html(rent_items)
        r = mock_response(html)
        results = HomeResults("woonzeker", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkstraat 10 A"


class TestParseRoofz:
    def _make_nuxt_html(self, rent_items, mapping=None):
        """Build minimal Nuxt IIFE HTML for roofz parser testing."""
        if mapping is None:
            mapping = {}

        func_args = list(mapping.keys()) if mapping else ["a"]
        params = list(mapping.values()) if mapping else ['"unused"']

        func_args_str = ",".join(func_args)
        params_str = ",".join(params)

        rent_js = json.dumps(rent_items)

        script = f"""<script>window.__NUXT__=(function({func_args_str}){{return {{rent:{rent_js}}}}})({params_str}));</script>"""
        return f"<html>{script}</html>"

    def test_basic_parsing(self, mock_response):
        rent_items = [
            {
                "status": "available",
                "slug": "kerkstraat-10-amsterdam",
                "address": {
                    "street": "Kerkstraat",
                    "houseNumber": 10,
                    "houseNumberExtension": "",
                    "location": "Amsterdam"
                },
                "handover": {"price": 1500}
            }
        ]
        html = self._make_nuxt_html(rent_items)
        r = mock_response(html)
        results = HomeResults("roofz", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkstraat 10"
        assert results[0].city == "Amsterdam"
        assert results[0].price == 1500
        assert "roofz.eu/availability/" in results[0].url

    def test_with_extension(self, mock_response):
        rent_items = [
            {
                "status": "available",
                "slug": "kerkstraat-10a",
                "address": {
                    "street": "Kerkstraat",
                    "houseNumber": 10,
                    "houseNumberExtension": "A",
                    "location": "Amsterdam"
                },
                "handover": {"price": 1500}
            }
        ]
        html = self._make_nuxt_html(rent_items)
        r = mock_response(html)
        results = HomeResults("roofz", r)
        assert results[0].address == "Kerkstraat 10 A"

    def test_filters_rented(self, mock_response):
        rent_items = [
            {
                "status": "rented",
                "slug": "straat-1",
                "address": {
                    "street": "Straat",
                    "houseNumber": 1,
                    "houseNumberExtension": "",
                    "location": "Amsterdam"
                },
                "handover": {"price": 1000}
            }
        ]
        html = self._make_nuxt_html(rent_items)
        r = mock_response(html)
        results = HomeResults("roofz", r)
        assert len(results.homes) == 0

    def test_filters_under_option(self, mock_response):
        rent_items = [
            {
                "status": "under option",
                "slug": "straat-1",
                "address": {
                    "street": "Straat",
                    "houseNumber": 1,
                    "houseNumberExtension": "",
                    "location": "Amsterdam"
                },
                "handover": {"price": 1000}
            }
        ]
        html = self._make_nuxt_html(rent_items)
        r = mock_response(html)
        results = HomeResults("roofz", r)
        assert len(results.homes) == 0

    def test_filters_missing_street(self, mock_response):
        rent_items = [
            {
                "status": "available",
                "slug": "unknown",
                "address": {
                    "street": "",
                    "houseNumber": 1,
                    "location": "Amsterdam"
                },
                "handover": {"price": 1000}
            }
        ]
        html = self._make_nuxt_html(rent_items)
        r = mock_response(html)
        results = HomeResults("roofz", r)
        assert len(results.homes) == 0

    def test_no_nuxt_script(self, mock_response):
        html = "<html><body>No nuxt data</body></html>"
        r = mock_response(html)
        results = HomeResults("roofz", r)
        assert len(results.homes) == 0


class TestParseVanderLinden:
    def _make_listing_html(self, address="Kerkstraat 10", city="Leiden",
                           price="€ 1.200 per maand", url="/woning/1",
                           label=None, include_all=True):
        html = '<div class="woninginfo">'
        if label:
            html += f'<div class="fotolabel">{label}</div>'
        if include_all:
            html += f'<strong>{address}</strong>'
            html += f'<div class="text-80 mb-0">{city}</div>'
            html += f'<div class="mt-2">{price}</div>'
            html += f'<a class="blocklink" href="{url}"></a>'
        html += '</div>'
        return f"<html>{html}</html>"

    def test_basic_parsing(self, mock_response):
        html = self._make_listing_html()
        r = mock_response(html)
        results = HomeResults("vanderlinden", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkstraat 10"
        assert results[0].city == "Leiden"
        assert results[0].price == 1200
        assert "vanderlinden.nl/woning/1" in results[0].url

    def test_filters_onder_optie(self, mock_response):
        html = self._make_listing_html(label="Onder optie")
        r = mock_response(html)
        results = HomeResults("vanderlinden", r)
        assert len(results.homes) == 0

    def test_filters_no_house_number(self, mock_response):
        html = self._make_listing_html(address="Nieuwbouwproject")
        r = mock_response(html)
        results = HomeResults("vanderlinden", r)
        assert len(results.homes) == 0

    def test_price_range_takes_lowest(self, mock_response):
        html = self._make_listing_html(price="€ 1.090 - 1.160")
        r = mock_response(html)
        results = HomeResults("vanderlinden", r)
        assert results[0].price == 1090

    def test_skips_op_aanvraag(self, mock_response):
        html = self._make_listing_html(price="Op aanvraag")
        r = mock_response(html)
        results = HomeResults("vanderlinden", r)
        assert len(results.homes) == 0

    def test_missing_elements(self, mock_response):
        html = self._make_listing_html(include_all=False)
        r = mock_response(html)
        results = HomeResults("vanderlinden", r)
        assert len(results.homes) == 0


class TestParseHoekstra:
    def test_parses_api_payload(self, mock_response):
        data = {
            "items": [
                {
                    "id": "abc-123",
                    "status": "Beschikbaar",
                    "street": "Kerkstraat",
                    "houseNumber": "10",
                    "houseNumberAddition": "A",
                    "city": "Leeuwarden",
                    "rentPrice": "1250"
                }
            ]
        }
        r = mock_response(data)
        results = HomeResults("hoekstra", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkstraat 10A"
        assert results[0].city == "Leeuwarden"
        assert results[0].price == 1250
        assert results[0].url == "https://verhuur.makelaardijhoekstra.nl/property-detail.html?id=abc-123"

    def test_api_filters_unavailable_status(self, mock_response):
        data = {
            "items": [
                {
                    "id": "x-1",
                    "status": "Onder Optie",
                    "street": "Kerkstraat",
                    "houseNumber": "10",
                    "city": "Leeuwarden",
                    "rentPrice": "1250"
                },
                {
                    "id": "x-2",
                    "status": "Verhuurd",
                    "street": "Havenstraat",
                    "houseNumber": "5",
                    "city": "Drachten",
                    "rentPrice": "995"
                }
            ]
        }
        r = mock_response(data)
        results = HomeResults("hoekstra", r)
        assert len(results.homes) == 0

    def test_api_filters_other_unavailable_statuses(self, mock_response):
        data = {
            "items": [
                {
                    "id": "x-3",
                    "status": "RentedWithReservation",
                    "street": "Astraat",
                    "houseNumber": "1",
                    "city": "Leeuwarden",
                    "rentPrice": "1000"
                },
                {
                    "id": "x-4",
                    "status": "Withdrawn",
                    "street": "Bstraat",
                    "houseNumber": "2",
                    "city": "Drachten",
                    "rentPrice": "1100"
                }
            ]
        }
        r = mock_response(data)
        results = HomeResults("hoekstra", r)
        assert len(results.homes) == 0

    def test_api_accepts_available_from_availability_field(self, mock_response):
        data = {
            "items": [
                {
                    "id": "x-5",
                    "status": "",
                    "availability": {"availability": "Immediatelly"},
                    "street": "Cstraat",
                    "houseNumber": "3",
                    "city": "Sneek",
                    "rentPrice": "1200"
                }
            ]
        }
        r = mock_response(data)
        results = HomeResults("hoekstra", r)
        assert len(results.homes) == 1
        assert results[0].address == "Cstraat 3"
        assert results[0].city == "Sneek"
        assert results[0].price == 1200

    def test_parses_json_ld_itemlist(self, mock_response):
        data = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "item": {
                        "@type": "Apartment",
                        "name": "Kerkstraat 10, Leeuwarden",
                        "url": "/aanbod/kerkstraat-10",
                        "address": {
                            "@type": "PostalAddress",
                            "streetAddress": "Kerkstraat 10",
                            "addressLocality": "Leeuwarden"
                        },
                        "offers": {
                            "@type": "Offer",
                            "price": "1.250",
                            "availability": "https://schema.org/InStock"
                        }
                    }
                }
            ]
        }
        html = f'<html><script type="application/ld+json">{json.dumps(data)}</script></html>'
        r = mock_response(html)
        results = HomeResults("hoekstra", r)
        assert len(results.homes) == 1
        assert results[0].address == "Kerkstraat 10"
        assert results[0].city == "Leeuwarden"
        assert results[0].price == 1250
        assert results[0].agency == "hoekstra"
        assert results[0].url == "https://verhuur.makelaardijhoekstra.nl/aanbod/kerkstraat-10"

    def test_filters_unavailable(self, mock_response):
        data = {
            "@type": "Apartment",
            "name": "Havenstraat 5, Drachten",
            "url": "/aanbod/havenstraat-5",
            "address": {
                "streetAddress": "Havenstraat 5",
                "addressLocality": "Drachten"
            },
            "offers": {
                "price": "995",
                "availability": "Verhuurd"
            }
        }
        html = f'<html><script type="application/ld+json">{json.dumps(data)}</script></html>'
        r = mock_response(html)
        results = HomeResults("hoekstra", r)
        assert len(results.homes) == 0

    def test_filters_no_house_number(self, mock_response):
        data = {
            "@type": "Apartment",
            "name": "Nieuwbouwproject, Heerenveen",
            "url": "/aanbod/nieuwbouwproject",
            "address": {
                "streetAddress": "Nieuwbouwproject",
                "addressLocality": "Heerenveen"
            },
            "offers": {"price": "1200"}
        }
        html = f'<html><script type="application/ld+json">{json.dumps(data)}</script></html>'
        r = mock_response(html)
        results = HomeResults("hoekstra", r)
        assert len(results.homes) == 0

    def test_html_fallback(self, mock_response):
        html = """
        <html>
            <article>
                <a href="/aanbod/sneek/klein-3">Bekijk</a>
                <h2 class="address">Klein 3</h2>
                <div class="city">Sneek</div>
                <div>€ 1.050 p/m</div>
            </article>
        </html>
        """
        r = mock_response(html)
        results = HomeResults("hoekstra", r)
        assert len(results.homes) == 1
        assert results[0].address == "Klein 3"
        assert results[0].city == "Sneek"
        assert results[0].price == 1050
        assert results[0].url == "https://verhuur.makelaardijhoekstra.nl/aanbod/sneek/klein-3"


class TestParseWooove:
    def test_basic_parsing(self, mock_response):
        html = """
        <div class="woningList clearer row">
            <a href="/Rotterdam/K.P.%20van%20der%20Mandelelaan-130-1105/35252304/tehuur.html">
                <div class="object">
                    <h2 class="adresregel">
                        <span class="straat"> K.P. van der Mandelelaan 130-1105</span>
                        <span class="plaats">Rotterdam</span>
                    </h2>
                    <div class="prijs">
                        <div>Huurprijs:&nbsp;€ 1.625,- p/m</div>
                    </div>
                </div>
            </a>
        </div>
        """
        r = mock_response(html)
        results = HomeResults("wooove", r)
        assert len(results.homes) == 1
        assert results[0].agency == "wooove"
        assert results[0].address == "K.P. van der Mandelelaan 130-1105"
        assert results[0].city == "Rotterdam"
        assert results[0].price == 1625
        assert results[0].url == "https://hurenbijwooove.nl/Rotterdam/K.P.%20van%20der%20Mandelelaan-130-1105/35252304/tehuur.html"

    def test_filters_unavailable_status(self, mock_response):
        html = """
        <div class="woningList clearer row">
            <a href="/Amsterdam/Koningin%20Wilhelminaplein-224/35249377/tehuur.html">
                <span class="statusbutton">Verhuurd onder voorbehoud</span>
                <h2 class="adresregel">
                    <span class="straat"> Koningin Wilhelminaplein 224</span>
                    <span class="plaats">Amsterdam</span>
                </h2>
                <div class="prijs"><div>Huurprijs:&nbsp;€ 1.870,- p/m</div></div>
            </a>
        </div>
        """
        r = mock_response(html)
        results = HomeResults("wooove", r)
        assert len(results.homes) == 0

    def test_filters_address_without_trackable_house_number(self, mock_response):
        html = """
        <div class="woningList clearer row">
            <a href="/Maastricht/Vijfharingenstraat-0ong/35267093/tehuur.html">
                <h2 class="adresregel">
                    <span class="straat"> Vijfharingenstraat 0ong</span>
                    <span class="plaats">Maastricht</span>
                </h2>
                <div class="prijs"><div>Huurprijs:&nbsp;€ 1.750,- p/m</div></div>
            </a>
        </div>
        """
        r = mock_response(html)
        results = HomeResults("wooove", r)
        assert len(results.homes) == 0


class TestSubstituteNuxtVars:
    def test_replaces_variables(self):
        js = '{street:a,city:b}'
        mapping = {"a": "Kerkstraat", "b": "Amsterdam"}
        result = HomeResults._substitute_nuxt_vars(js, mapping)
        assert '"Kerkstraat"' in result
        assert '"Amsterdam"' in result

    def test_preserves_quoted_strings(self):
        js = '{name:"hello",value:a}'
        mapping = {"a": "world"}
        result = HomeResults._substitute_nuxt_vars(js, mapping)
        assert '"hello"' in result
        assert '"world"' in result

    def test_preserves_keywords(self):
        js = '{active:true,data:null,value:a}'
        mapping = {"a": "test"}
        result = HomeResults._substitute_nuxt_vars(js, mapping)
        assert 'true' in result
        assert 'null' in result

    def test_escapes_special_chars_in_values(self):
        js = '{name:a}'
        mapping = {"a": 'he said "hi"'}
        result = HomeResults._substitute_nuxt_vars(js, mapping)
        assert '\\"' in result

    def test_unmapped_identifier_preserved(self):
        js = '{name:unknownVar}'
        mapping = {}
        result = HomeResults._substitute_nuxt_vars(js, mapping)
        assert 'unknownVar' in result

    def test_empty_input(self):
        result = HomeResults._substitute_nuxt_vars('', {})
        assert result == ''

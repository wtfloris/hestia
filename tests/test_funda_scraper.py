import json
import pytest
from unittest.mock import patch, MagicMock


TARGET = {
    "queryurl": "https://listing-search-wonen.funda.nl/_msearch/template",
    "headers": {
        "Content-Type": "application/x-ndjson",
        "Referer": "https://www.funda.nl/",
        "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
        "User-Agent": "Mozilla/5.0",
    },
    "post_data": [
        {"index": "listings-wonen-searcher-alias-prod"},
        {"id": "search_result_20260227", "params": {}},
    ],
}

SEARCH_RESULT = {
    "responses": [
        {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "address": {
                                "street_name": "Kerkstraat",
                                "house_number": "10",
                                "city": "Amsterdam",
                            },
                            "price": {"rent_price": [1625]},
                            "object_detail_page_relative_url": "/detail/huur/amsterdam/appartement-kerkstraat-10/123/",
                            "floor_area": [65],
                        }
                    }
                ]
            }
        }
    ]
}


def _mock_session(search_status=200, prime_status=200, search_body=None):
    prime = MagicMock()
    prime.status_code = prime_status

    search = MagicMock()
    search.status_code = search_status
    search.content = json.dumps(search_body if search_body is not None else SEARCH_RESULT).encode("utf-8")
    search.headers = {}

    session = MagicMock()
    session.get.return_value = prime
    session.post.return_value = search

    return session, patch("hestia_utils.funda_scraper.requests.Session", return_value=session)


class TestScrapeFunda:
    def test_basic_parsing(self):
        from hestia_utils.funda_scraper import scrape_funda

        session, patcher = _mock_session()
        with patcher:
            homes = scrape_funda(TARGET)

        assert len(homes) == 1
        assert homes[0].agency == "funda"
        assert homes[0].address == "Kerkstraat 10"
        assert homes[0].city == "Amsterdam"
        assert homes[0].price == 1625
        assert homes[0].sqm == 65

    def test_primes_session_before_searching(self):
        # Akamai only serves the search API to a session holding a bm_s cookie,
        # so the public site must be fetched first, on the same session.
        from hestia_utils.funda_scraper import scrape_funda

        session, patcher = _mock_session()
        with patcher:
            scrape_funda(TARGET)

        session.get.assert_called_once()
        assert session.get.call_args[0][0] == "https://www.funda.nl/"
        assert session.mount.called

    def test_body_is_ndjson(self):
        from hestia_utils.funda_scraper import scrape_funda

        session, patcher = _mock_session()
        with patcher:
            scrape_funda(TARGET)

        body = session.post.call_args[1]["data"]
        assert body.endswith("\n")
        lines = body.strip("\n").split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == TARGET["post_data"][0]

    def test_non_ok_search_raises(self):
        from hestia_utils.funda_scraper import scrape_funda

        _, patcher = _mock_session(search_status=403)
        with patcher, pytest.raises(ConnectionError, match="non-OK status code"):
            scrape_funda(TARGET)

    def test_non_ok_prime_raises(self):
        from hestia_utils.funda_scraper import scrape_funda

        _, patcher = _mock_session(prime_status=503)
        with patcher, pytest.raises(ConnectionError, match="priming the session"):
            scrape_funda(TARGET)

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from hestia_utils.parser import Home


class TestScrapeSite:
    @patch('scraper.broadcast', new_callable=AsyncMock)
    @patch('scraper.db')
    @patch('scraper.requests')
    def test_new_homes_written_and_broadcast(self, mock_requests, mock_db, mock_broadcast):
        from scraper import scrape_site

        # Mock GET response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response

        # Mock HomeResults to return one home
        test_home = Home(address="Kerkstraat 10", city="Amsterdam", url="http://test.com", agency="rebo", price=1500)
        with patch('scraper.HomeResults') as mock_hr:
            mock_hr.return_value = [test_home]

            # No previous homes in DB
            mock_db.fetch_all.side_effect = [
                [],  # previous homes query
            ]

            target = {
                "id": 1,
                "agency": "rebo",
                "queryurl": "http://api.test.com",
                "method": "GET",
                "headers": {},
                "post_data": None
            }

            import asyncio
            asyncio.get_event_loop().run_until_complete(scrape_site(target))

            mock_db.add_home.assert_called_once()
            mock_broadcast.assert_called_once()
            broadcast_homes = mock_broadcast.call_args[0][0]
            assert len(broadcast_homes) == 1
            assert broadcast_homes[0].address == "Kerkstraat 10"

    @patch('scraper.broadcast', new_callable=AsyncMock)
    @patch('scraper.db')
    @patch('scraper.requests')
    def test_non_200_raises_connection_error(self, mock_requests, mock_db, mock_broadcast):
        from scraper import scrape_site

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_requests.get.return_value = mock_response

        target = {
            "id": 1, "agency": "rebo", "queryurl": "http://api.test.com",
            "method": "GET", "headers": {}, "post_data": None
        }

        import asyncio
        with pytest.raises(ConnectionError, match="non-OK status code"):
            asyncio.get_event_loop().run_until_complete(scrape_site(target))

    @patch('scraper.broadcast', new_callable=AsyncMock)
    @patch('scraper.db')
    @patch('scraper.requests')
    def test_post_method(self, mock_requests, mock_db, mock_broadcast):
        from scraper import scrape_site

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        with patch('scraper.HomeResults') as mock_hr:
            mock_hr.return_value = []
            mock_db.fetch_all.return_value = []

            target = {
                "id": 1, "agency": "funda", "queryurl": "http://api.test.com",
                "method": "POST", "headers": {"Content-Type": "application/json"},
                "post_data": {"query": "test"}
            }

            import asyncio
            asyncio.get_event_loop().run_until_complete(scrape_site(target))

            mock_requests.post.assert_called_once_with(
                "http://api.test.com",
                json={"query": "test"},
                headers={"Content-Type": "application/json"}
            )

    @patch('scraper.broadcast', new_callable=AsyncMock)
    @patch('scraper.db')
    @patch('scraper.requests')
    def test_post_ndjson_method(self, mock_requests, mock_db, mock_broadcast):
        from scraper import scrape_site

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        with patch('scraper.HomeResults') as mock_hr:
            mock_hr.return_value = []
            mock_db.fetch_all.return_value = []

            target = {
                "id": 1, "agency": "funda", "queryurl": "http://api.test.com",
                "method": "POST_NDJSON", "headers": {},
                "post_data": [{"index": "test"}, {"query": "match_all"}]
            }

            import asyncio
            asyncio.get_event_loop().run_until_complete(scrape_site(target))

            call_args = mock_requests.post.call_args
            assert call_args[1]["data"].count("\n") == 2  # Two NDJSON lines

    @patch('scraper.broadcast', new_callable=AsyncMock)
    @patch('scraper.db')
    @patch('scraper.requests')
    def test_unknown_method_raises(self, mock_requests, mock_db, mock_broadcast):
        from scraper import scrape_site

        target = {
            "id": 1, "agency": "test", "queryurl": "http://api.test.com",
            "method": "DELETE", "headers": {}, "post_data": None
        }

        import asyncio
        with pytest.raises(ValueError, match="Unknown method"):
            asyncio.get_event_loop().run_until_complete(scrape_site(target))

    @patch('scraper.broadcast', new_callable=AsyncMock)
    @patch('scraper.db')
    @patch('scraper.requests')
    def test_deduplication(self, mock_requests, mock_db, mock_broadcast):
        from scraper import scrape_site

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response

        existing_home = Home(address="Kerkstraat 10", city="Amsterdam")
        new_home = Home(address="Kerkstraat 10", city="Amsterdam", url="http://test.com", agency="rebo", price=1500)
        brand_new = Home(address="Dorpsweg 5", city="Rotterdam", url="http://test.com/2", agency="rebo", price=1200)

        with patch('scraper.HomeResults') as mock_hr:
            mock_hr.return_value = [new_home, brand_new]
            mock_db.fetch_all.return_value = [
                {"address": "Kerkstraat 10", "city": "Amsterdam"}
            ]

            target = {
                "id": 1, "agency": "rebo", "queryurl": "http://api.test.com",
                "method": "GET", "headers": {}, "post_data": None
            }

            import asyncio
            asyncio.get_event_loop().run_until_complete(scrape_site(target))

            # Only brand_new should be added
            assert mock_db.add_home.call_count == 1
            call_args = mock_db.add_home.call_args[0]
            assert call_args[1] == "Dorpsweg 5"


class TestBroadcast:
    @pytest.mark.asyncio
    @patch('scraper.meta')
    @patch('scraper.db')
    async def test_applies_price_filter(self, mock_db, mock_meta):
        from scraper import broadcast

        mock_db.get_dev_mode.return_value = False
        mock_db.fetch_all.side_effect = [
            [{"telegram_id": 111, "filter_min_price": 1000, "filter_max_price": 1500,
              "filter_cities": ["amsterdam"], "filter_agencies": ["rebo"], "filter_min_sqm": 0}],
            [{"agency": "rebo", "user_info": {"agency": "Rebo"}}]
        ]
        mock_meta.BOT.send_message = AsyncMock()

        home_in_range = Home(address="Straat 1", city="Amsterdam", url="http://a.com", agency="rebo", price=1200)
        home_too_expensive = Home(address="Straat 2", city="Amsterdam", url="http://b.com", agency="rebo", price=2000)

        await broadcast([home_in_range, home_too_expensive])

        assert mock_meta.BOT.send_message.call_count == 1

    @pytest.mark.asyncio
    @patch('scraper.meta')
    @patch('scraper.db')
    async def test_applies_city_filter(self, mock_db, mock_meta):
        from scraper import broadcast

        mock_db.get_dev_mode.return_value = False
        mock_db.fetch_all.side_effect = [
            [{"telegram_id": 111, "filter_min_price": 0, "filter_max_price": 9999,
              "filter_cities": ["amsterdam"], "filter_agencies": ["rebo"], "filter_min_sqm": 0}],
            [{"agency": "rebo", "user_info": {"agency": "Rebo"}}]
        ]
        mock_meta.BOT.send_message = AsyncMock()

        home_right_city = Home(address="Straat 1", city="Amsterdam", url="http://a.com", agency="rebo", price=1200)
        home_wrong_city = Home(address="Straat 2", city="Rotterdam", url="http://b.com", agency="rebo", price=1200)

        await broadcast([home_right_city, home_wrong_city])

        assert mock_meta.BOT.send_message.call_count == 1

    @pytest.mark.asyncio
    @patch('scraper.meta')
    @patch('scraper.db')
    async def test_forbidden_disables_user(self, mock_db, mock_meta):
        from scraper import broadcast
        from telegram.error import Forbidden

        mock_db.get_dev_mode.return_value = False
        mock_db.fetch_all.side_effect = [
            [{"telegram_id": 111, "filter_min_price": 0, "filter_max_price": 9999,
              "filter_cities": ["amsterdam"], "filter_agencies": ["rebo"], "filter_min_sqm": 0}],
            [{"agency": "rebo", "user_info": {"agency": "Rebo"}}]
        ]
        mock_meta.BOT.send_message = AsyncMock(side_effect=Forbidden("Forbidden: bot was blocked by the user"))

        home = Home(address="Straat 1", city="Amsterdam", url="http://a.com", agency="rebo", price=1200)

        await broadcast([home])

        mock_db.disable_user.assert_called_once_with(111)

    @pytest.mark.asyncio
    @patch('scraper.meta')
    @patch('scraper.db')
    async def test_applies_sqm_filter(self, mock_db, mock_meta):
        from scraper import broadcast

        mock_db.get_dev_mode.return_value = False
        mock_db.fetch_all.side_effect = [
            [{"telegram_id": 111, "filter_min_price": 0, "filter_max_price": 9999,
              "filter_cities": ["amsterdam"], "filter_agencies": ["rebo"], "filter_min_sqm": 40}],
            [{"agency": "rebo", "user_info": {"agency": "Rebo"}}]
        ]
        mock_meta.BOT.send_message = AsyncMock()

        home_big = Home(address="Straat 1", city="Amsterdam", url="http://a.com", agency="rebo", price=1200, sqm=60)
        home_small = Home(address="Straat 2", city="Amsterdam", url="http://b.com", agency="rebo", price=1200, sqm=30)
        home_unknown = Home(address="Straat 3", city="Amsterdam", url="http://c.com", agency="rebo", price=1200, sqm=-1)

        await broadcast([home_big, home_small, home_unknown])

        # home_big (60 >= 40) and home_unknown (-1, passes) should be sent; home_small (30 < 40) filtered
        assert mock_meta.BOT.send_message.call_count == 2

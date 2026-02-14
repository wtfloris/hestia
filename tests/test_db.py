from unittest.mock import patch, MagicMock
from datetime import datetime

import hestia_utils.db as db


def _mock_connection(rows=None, fetchone_val="__unset__", side_effect=None):
    """Helper: create a mock psycopg2 connection + cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    # Use the MagicMock's built-in context manager support
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    if fetchone_val != "__unset__":
        mock_cursor.fetchone.return_value = fetchone_val
    if rows is not None:
        mock_cursor.fetchall.return_value = rows
    if side_effect is not None:
        mock_cursor.execute.side_effect = side_effect
    return mock_conn, mock_cursor


class TestFetchOne:
    @patch('hestia_utils.db.get_connection')
    def test_returns_dict_on_success(self, mock_get_conn):
        mock_conn, mock_cursor = _mock_connection(fetchone_val={"id": 1, "name": "test"})
        mock_get_conn.return_value = mock_conn
        result = db.fetch_one("SELECT * FROM test WHERE id = %s", [1])
        assert result == {"id": 1, "name": "test"}

    @patch('hestia_utils.db.get_connection')
    def test_returns_empty_dict_on_no_result(self, mock_get_conn):
        mock_conn, mock_cursor = _mock_connection(fetchone_val=None)
        mock_get_conn.return_value = mock_conn
        result = db.fetch_one("SELECT * FROM test WHERE id = %s", [999])
        assert result == {}

    @patch('hestia_utils.db.get_connection')
    def test_returns_empty_dict_on_exception(self, mock_get_conn):
        mock_conn, mock_cursor = _mock_connection(side_effect=Exception("DB error"))
        mock_get_conn.return_value = mock_conn
        result = db.fetch_one("INVALID SQL")
        assert result == {}


class TestFetchAll:
    @patch('hestia_utils.db.get_connection')
    def test_returns_list_on_success(self, mock_get_conn):
        rows = [{"id": 1}, {"id": 2}]
        mock_conn, mock_cursor = _mock_connection(rows=rows)
        mock_get_conn.return_value = mock_conn
        result = db.fetch_all("SELECT * FROM test")
        assert result == rows

    @patch('hestia_utils.db.get_connection')
    def test_returns_empty_list_on_exception(self, mock_get_conn):
        mock_conn, mock_cursor = _mock_connection(side_effect=Exception("DB error"))
        mock_get_conn.return_value = mock_conn
        result = db.fetch_all("INVALID SQL")
        assert result == []


class TestGetDevMode:
    @patch('hestia_utils.db.fetch_one')
    def test_returns_true_when_enabled(self, mock_fetch):
        mock_fetch.return_value = {"devmode_enabled": True}
        assert db.get_dev_mode() is True

    @patch('hestia_utils.db.fetch_one')
    def test_returns_false_when_disabled(self, mock_fetch):
        mock_fetch.return_value = {"devmode_enabled": False}
        assert db.get_dev_mode() is False

    @patch('hestia_utils.db.fetch_one')
    def test_returns_true_on_empty_result(self, mock_fetch):
        mock_fetch.return_value = {}
        assert db.get_dev_mode() is True


class TestGetScraperHalted:
    @patch('hestia_utils.db.fetch_one')
    def test_returns_false_when_not_halted(self, mock_fetch):
        mock_fetch.return_value = {"scraper_halted": False}
        assert db.get_scraper_halted() is False

    @patch('hestia_utils.db.fetch_one')
    def test_returns_true_when_halted(self, mock_fetch):
        mock_fetch.return_value = {"scraper_halted": True}
        assert db.get_scraper_halted() is True

    @patch('hestia_utils.db.fetch_one')
    def test_returns_true_on_empty_result(self, mock_fetch):
        mock_fetch.return_value = {}
        assert db.get_scraper_halted() is True


class TestGetDonationLink:
    @patch('hestia_utils.db.fetch_one')
    def test_returns_link(self, mock_fetch):
        mock_fetch.return_value = {"donation_link": "https://tikkie.me/abc"}
        assert db.get_donation_link() == "https://tikkie.me/abc"

    @patch('hestia_utils.db.fetch_one')
    def test_returns_empty_on_no_result(self, mock_fetch):
        mock_fetch.return_value = {}
        assert db.get_donation_link() == ""


class TestGetDonationLinkUpdated:
    @patch('hestia_utils.db.fetch_one')
    def test_returns_datetime(self, mock_fetch):
        dt = datetime(2024, 1, 15, 12, 0, 0)
        mock_fetch.return_value = {"donation_link_updated": dt}
        assert db.get_donation_link_updated() == dt

    @patch('hestia_utils.db.fetch_one')
    def test_returns_min_on_empty(self, mock_fetch):
        mock_fetch.return_value = {}
        assert db.get_donation_link_updated() == datetime.min


class TestGetUserLang:
    def setup_method(self):
        db.LANG_CACHE.clear()

    @patch('hestia_utils.db.fetch_one')
    def test_returns_user_language(self, mock_fetch):
        mock_fetch.return_value = {"lang": "nl"}
        assert db.get_user_lang(111) == "nl"

    @patch('hestia_utils.db.fetch_one')
    def test_caches_result(self, mock_fetch):
        mock_fetch.return_value = {"lang": "nl"}
        db.get_user_lang(222)
        db.get_user_lang(222)
        mock_fetch.assert_called_once()

    @patch('hestia_utils.db.fetch_one')
    def test_returns_en_by_default(self, mock_fetch):
        mock_fetch.return_value = {}
        assert db.get_user_lang(333) == "en"

    @patch('hestia_utils.db.fetch_one')
    def test_returns_en_for_invalid_lang(self, mock_fetch):
        mock_fetch.return_value = {"lang": "de"}
        assert db.get_user_lang(444) == "en"


class TestWriteActions:
    @patch('hestia_utils.db._write')
    def test_add_home(self, mock_write):
        db.add_home("http://example.com", "Kerkstraat 1", "Amsterdam", 1500, "funda", "2024-01-01")
        mock_write.assert_called_once()
        args = mock_write.call_args[0]
        assert "INSERT INTO hestia.homes" in args[0]
        assert "http://example.com" in args[1]

    @patch('hestia_utils.db._write')
    def test_add_user(self, mock_write):
        db.add_user(12345)
        mock_write.assert_called_once()
        assert "INSERT INTO hestia.subscribers" in mock_write.call_args[0][0]

    @patch('hestia_utils.db._write')
    def test_enable_user(self, mock_write):
        db.enable_user(12345)
        mock_write.assert_called_once()
        assert "telegram_enabled = true" in mock_write.call_args[0][0]

    @patch('hestia_utils.db._write')
    def test_disable_user(self, mock_write):
        db.disable_user(12345)
        mock_write.assert_called_once()
        assert "telegram_enabled = false" in mock_write.call_args[0][0]

    @patch('hestia_utils.db._write')
    def test_halt_scraper(self, mock_write):
        db.halt_scraper()
        mock_write.assert_called_once()
        assert "scraper_halted = true" in mock_write.call_args[0][0]

    @patch('hestia_utils.db._write')
    def test_resume_scraper(self, mock_write):
        db.resume_scraper()
        mock_write.assert_called_once()
        assert "scraper_halted = false" in mock_write.call_args[0][0]


class TestLinkAccount:
    @patch('hestia_utils.db.get_connection')
    def test_invalid_code(self, mock_get_conn):
        mock_conn, mock_cursor = _mock_connection(fetchone_val=None)
        mock_get_conn.return_value = mock_conn
        result = db.link_account(12345, "XXXX")
        assert result == "invalid_code"

    @patch('hestia_utils.db.get_connection')
    def test_already_linked(self, mock_get_conn):
        mock_conn, mock_cursor = _mock_connection()
        # First call: find the code -> return email
        # Second call: check if telegram user has email -> yes
        mock_cursor.fetchone.side_effect = [
            {"email_address": "user@test.com"},  # code lookup
            {"email_address": "existing@test.com"},  # already linked
        ]
        mock_get_conn.return_value = mock_conn
        result = db.link_account(12345, "ABCD")
        assert result == "already_linked"

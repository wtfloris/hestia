from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def geocode_module():
    import hestia_utils.geocode as geocode
    return geocode


class TestNormalizeAddress:
    def test_strips_unit_suffix(self, geocode_module):
        assert geocode_module.normalize_address("Damstraat 12 3hg") == "Damstraat 12"
        assert geocode_module.normalize_address("Damstraat 12 B2") == "Damstraat 12"

    def test_collapses_whitespace(self, geocode_module):
        assert geocode_module.normalize_address("  Damstraat   12  ") == "Damstraat 12"

    def test_handles_plain_address(self, geocode_module):
        assert geocode_module.normalize_address("Kerkstraat 10") == "Kerkstraat 10"

    def test_empty(self, geocode_module):
        assert geocode_module.normalize_address("") == ""


class TestHaversine:
    def test_same_point_is_zero(self, geocode_module):
        assert geocode_module.haversine_km(52.3676, 4.9041, 52.3676, 4.9041) == pytest.approx(0.0, abs=1e-6)

    def test_amsterdam_rotterdam_approx(self, geocode_module):
        # Amsterdam Centraal to Rotterdam Centraal ~ 57km
        d = geocode_module.haversine_km(52.3791, 4.9003, 51.9244, 4.4695)
        assert 55 < d < 60

    def test_symmetric(self, geocode_module):
        a = geocode_module.haversine_km(52.0, 4.0, 51.0, 5.0)
        b = geocode_module.haversine_km(51.0, 5.0, 52.0, 4.0)
        assert a == pytest.approx(b)


class TestParsePoint:
    def test_parses_valid_point(self, geocode_module):
        assert geocode_module._parse_point("POINT(4.9041 52.3676)") == (52.3676, 4.9041)

    def test_none_on_garbage(self, geocode_module):
        assert geocode_module._parse_point("") is None
        assert geocode_module._parse_point("garbage") is None


class TestGeocode:
    @patch("hestia_utils.geocode.requests.get")
    @patch("hestia_utils.geocode.db")
    def test_hits_cache_before_pdok(self, mock_db, mock_get, geocode_module):
        mock_db.fetch_one.return_value = {"lat": 52.37, "lon": 4.90, "confidence": 9.5}
        result = geocode_module.geocode("Damstraat 1", "Amsterdam")
        assert result == (52.37, 4.90, 9.5)
        mock_get.assert_not_called()

    @patch("hestia_utils.geocode.requests.get")
    @patch("hestia_utils.geocode.db")
    def test_cached_null_means_known_miss(self, mock_db, mock_get, geocode_module):
        mock_db.fetch_one.return_value = {"lat": None, "lon": None, "confidence": None}
        assert geocode_module.geocode("Unknown", "Nowhere") is None
        mock_get.assert_not_called()

    @patch("hestia_utils.geocode.requests.get")
    @patch("hestia_utils.geocode.db")
    def test_pdok_success_writes_cache(self, mock_db, mock_get, geocode_module):
        mock_db.fetch_one.return_value = {}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {
                "docs": [{"score": 9.5, "centroide_ll": "POINT(4.9041 52.3676)"}]
            }
        }
        mock_get.return_value = mock_response

        result = geocode_module.geocode("Damstraat 1", "Amsterdam")
        assert result == (52.3676, 4.9041, 9.5)
        mock_db._write.assert_called_once()
        # Cache write parameters: (address, city, lat, lon, confidence)
        args = mock_db._write.call_args[0][1]
        assert args[:2] == ["Damstraat 1", "Amsterdam"]
        assert args[2] == 52.3676
        assert args[3] == 4.9041

    @patch("hestia_utils.geocode.requests.get")
    @patch("hestia_utils.geocode.db")
    def test_pdok_empty_caches_null(self, mock_db, mock_get, geocode_module):
        mock_db.fetch_one.return_value = {}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"docs": []}}
        mock_get.return_value = mock_response

        # Both lookups (adres + weergavenaam fallback) return empty → None.
        assert geocode_module.geocode("Nowhere", "Atlantis") is None
        assert mock_db._write.called
        args = mock_db._write.call_args[0][1]
        # lat/lon/confidence are all NULL for a known-miss.
        assert args[2] is None
        assert args[3] is None
        assert args[4] is None

    @patch("hestia_utils.geocode.requests.get")
    @patch("hestia_utils.geocode.db")
    def test_low_score_triggers_fallback(self, mock_db, mock_get, geocode_module):
        mock_db.fetch_one.return_value = {}

        first = MagicMock()
        first.status_code = 200
        first.json.return_value = {
            "response": {"docs": [{"score": 2.0, "centroide_ll": "POINT(1.0 1.0)"}]}
        }
        second = MagicMock()
        second.status_code = 200
        second.json.return_value = {
            "response": {"docs": [{"score": 5.0, "centroide_ll": "POINT(4.9 52.3)"}]}
        }
        mock_get.side_effect = [first, second]

        result = geocode_module.geocode("Amsterdam", "")
        # Fallback takes over because its score (5.0) beat the low type:adres hit (2.0).
        assert result == (52.3, 4.9, 0.0)

    @patch("hestia_utils.geocode.requests.get")
    @patch("hestia_utils.geocode.db")
    def test_network_error_returns_none(self, mock_db, mock_get, geocode_module):
        import requests as real_requests
        mock_db.fetch_one.return_value = {}
        mock_get.side_effect = real_requests.RequestException("boom")
        assert geocode_module.geocode("x", "y") is None

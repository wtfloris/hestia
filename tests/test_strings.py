from unittest.mock import patch
from hestia_utils.strings import get, _STRINGS


class TestGetDefaultLanguage:
    @patch('hestia_utils.strings.get_user_lang', return_value="en")
    def test_returns_english_by_default(self, mock_lang):
        result = get("already_subscribed")
        assert "already subscribed" in result

    @patch('hestia_utils.strings.get_user_lang', return_value="en")
    def test_returns_english_with_telegram_id(self, mock_lang):
        result = get("already_subscribed", telegram_id=123)
        assert "already subscribed" in result


class TestGetDutchLanguage:
    @patch('hestia_utils.strings.get_user_lang', return_value="nl")
    def test_returns_dutch(self, mock_lang):
        result = get("already_subscribed", telegram_id=123)
        assert "al geregistreerd" in result


class TestGetWithParams:
    @patch('hestia_utils.strings.get_user_lang', return_value="en")
    def test_substitutes_params(self, mock_lang):
        result = get("filter_minprice", telegram_id=123, params=["1200"])
        assert "1200" in result

    @patch('hestia_utils.strings.get_user_lang', return_value="en")
    def test_stop_with_donation_link(self, mock_lang):
        result = get("stop", telegram_id=123, params=["https://tikkie.me/test"])
        assert "https://tikkie.me/test" in result


class TestGetInvalidKey:
    def test_invalid_key_returns_fallback(self):
        result = get("nonexistent_key_12345")
        assert "string undefined" in result
        assert "nonexistent_key_12345" in result


class TestAllStringsValid:
    @patch('hestia_utils.strings.get_user_lang', return_value="en")
    def test_all_keys_have_english(self, mock_lang):
        for key in _STRINGS:
            assert "en" in _STRINGS[key], f"Key '{key}' missing English translation"

    def test_all_keys_with_dutch_have_both(self):
        for key, langs in _STRINGS.items():
            if "nl" in langs:
                assert "en" in langs, f"Key '{key}' has Dutch but missing English"

    @patch('hestia_utils.strings.get_user_lang', return_value="en")
    def test_all_keys_return_nonempty_english(self, mock_lang):
        # Keys that need params to format properly
        param_keys = {"stop", "filter", "filter_minprice", "filter_maxprice",
                      "filter_city_invalid", "filter_city_already_in",
                      "filter_city_added", "filter_city_not_in",
                      "filter_city_removed", "filter_invalid_number",
                      "donate", "faq", "website_info"}
        for key in _STRINGS:
            if key not in param_keys:
                result = get(key)
                assert len(result) > 0, f"Key '{key}' returned empty string"

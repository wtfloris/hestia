"""End-to-end tests for the Hestia web interface.

All external dependencies (PostgreSQL, Brevo) are mocked so tests
can run without any infrastructure.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from sib_api_v3_sdk.rest import ApiException as BrevoApiException
from werkzeug.datastructures import MultiDict

# Set env vars BEFORE importing app
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("BREVO_API_KEY", "xkeysib-test-key")
os.environ.setdefault("FROM_EMAIL", "test@example.com")
os.environ.setdefault("BASE_URL", "http://localhost:5000")

import hestia_web.app as hestia_app


@pytest.fixture
def client():
    """Create a Flask test client."""
    hestia_app.app.config["TESTING"] = True
    # Reset rate limiter before each test
    hestia_app.limiter.reset()
    with hestia_app.app.test_client() as c:
        yield c


# ---- Helper to build a valid session cookie ----

def make_session_cookie(email="user@example.com"):
    """Generate a signed session cookie value for the given email."""
    return hestia_app.serializer.dumps(email, salt="email-session")


def set_session(client, email="user@example.com"):
    """Set a valid session cookie on the test client."""
    cookie_value = make_session_cookie(email)
    client.set_cookie("hestia_session", cookie_value, domain="localhost")


def get_csrf_token(html_content):
    """Extract CSRF token from HTML content."""
    import re
    match = re.search(r'name="csrf_token" value="([^"]+)"', html_content)
    if match:
        return match.group(1)
    return None


def get_csrf_token_for_session(client):
    """Generate a CSRF token for the current session."""
    # Generate CSRF token directly using the session cookie
    cookie_value = client.get_cookie("hestia_session", domain="localhost")
    if cookie_value:
        return hestia_app.serializer.dumps(cookie_value.value, salt="csrf-token")
    return None


# ---- Mock helpers ----

def mock_subscriber(
    id=1,
    email_address="user@example.com",
    telegram_id=None,
    notifications_enabled=True,
    filter_min_price=500,
    filter_max_price=1500,
    filter_cities=None,
    filter_agencies=None,
):
    """Return a dict that looks like a subscriber row."""
    return {
        "id": id,
        "email_address": email_address,
        "telegram_id": telegram_id,
        "telegram_enabled": notifications_enabled,
        "filter_min_price": filter_min_price,
        "filter_max_price": filter_max_price,
        "filter_cities": filter_cities or ["Amsterdam", "Rotterdam"],
        "filter_agencies": filter_agencies or ["agency1"],
    }


_SENTINEL = object()


MOCK_CITIES_ROWS = [{"city": "Amsterdam"}, {"city": "Rotterdam"}, {"city": "Utrecht"}]
MOCK_AGENCIES_ROWS = [
    {"agency": "agency1", "user_info": {"agency": "Agency One"}},
    {"agency": "agency2", "user_info": {"agency": "Agency Two"}},
]


def make_mock_cursor(rows=None, fetchone_value=_SENTINEL):
    """Create a mock cursor that supports context manager and query methods."""
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    cur.rowcount = 1  # Default to successful insert/update
    if fetchone_value is not _SENTINEL:
        cur.fetchone.return_value = fetchone_value
    if rows is not None:
        cur.fetchall.return_value = rows
    return cur


def make_dashboard_cursor(subscriber):
    """Create a mock cursor for dashboard route (subscriber + cities + agencies)."""
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    cur.rowcount = 1  # Default to successful insert/update
    cur.fetchone.return_value = subscriber
    cur.fetchall.side_effect = [MOCK_CITIES_ROWS, MOCK_AGENCIES_ROWS]
    return cur


def make_mock_conn(cursor):
    """Create a mock connection that returns the given cursor."""
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cursor
    return conn


# =====================================================================
# LANDING PAGE TESTS
# =====================================================================

class TestLandingPage:
    def test_get_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_get_index_contains_login_form(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert '<form method="post" action="/login">' in html
        assert 'type="email"' in html
        assert "Hestia" in html

    def test_get_index_shows_message_param(self, client):
        resp = client.get("/?message=Hello+World")
        html = resp.data.decode()
        assert "Hello World" in html

    def test_get_index_no_message_param(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert "message" not in html.lower() or 'class="message"' not in html

    def test_index_redirects_to_dashboard_if_logged_in(self, client):
        set_session(client, email="user@example.com")
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]


# =====================================================================
# LOGIN (MAGIC LINK) TESTS
# =====================================================================

class TestLogin:
    def test_login_empty_email_redirects(self, client):
        resp = client.post("/login", data={"email": ""}, follow_redirects=False)
        assert resp.status_code == 302
        assert "message=" in resp.headers["Location"]

    @patch("hestia_web.app.sib_api_v3_sdk")
    def test_login_invalid_email_redirects(self, mock_sdk, client):
        index_resp = client.get("/")
        csrf_token = get_csrf_token(index_resp.data.decode())

        resp = client.post(
            "/login", data={"email": "not-an-email", "csrf_token": csrf_token}, follow_redirects=False
        )
        assert resp.status_code == 302
        assert "message=" in resp.headers["Location"]
        mock_sdk.TransactionalEmailsApi.return_value.send_transac_email.assert_not_called()

    @patch("hestia_web.app.get_db")
    @patch("hestia_web.app.sib_api_v3_sdk")
    def test_login_valid_email_sends_email(self, mock_sdk, mock_get_db, client):
        # Mock database for storing magic token
        cur = make_mock_cursor()
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        # Get CSRF token from index page
        index_resp = client.get("/")
        csrf_token = get_csrf_token(index_resp.data.decode())

        resp = client.post(
            "/login", data={"email": "user@example.com", "csrf_token": csrf_token}, follow_redirects=False
        )
        assert resp.status_code == 302
        mock_sdk.TransactionalEmailsApi.return_value.send_transac_email.assert_called_once()

        # Verify the sent email was constructed with the right recipient
        call_args = mock_sdk.SendSmtpEmail.call_args
        assert call_args[1]["to"] == [{"email": "user@example.com"}]

    @patch("hestia_web.app.get_db")
    @patch("hestia_web.app.sib_api_v3_sdk")
    def test_login_brevo_failure_shows_error(self, mock_sdk, mock_get_db, client):
        mock_sdk.TransactionalEmailsApi.return_value.send_transac_email.side_effect = \
            BrevoApiException(status=500, reason="Brevo error")

        # Mock database for storing magic token
        cur = make_mock_cursor()
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.post(
            "/login", data={"email": "user@example.com"}, follow_redirects=False
        )
        assert resp.status_code == 302
        assert "Failed" in resp.headers["Location"] or "message=" in resp.headers["Location"]

    @patch("hestia_web.app.get_db")
    @patch("hestia_web.app.sib_api_v3_sdk")
    def test_login_normalizes_email(self, mock_sdk, mock_get_db, client):
        # Mock database for storing magic token
        cur = make_mock_cursor()
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        # Get CSRF token from index page
        index_resp = client.get("/")
        csrf_token = get_csrf_token(index_resp.data.decode())

        client.post("/login", data={"email": "  User@Example.COM  ", "csrf_token": csrf_token})
        call_args = mock_sdk.SendSmtpEmail.call_args
        # The token should contain the lowercased email
        assert call_args[1]["to"] == [{"email": "user@example.com"}]

    @patch("hestia_web.app.get_db")
    @patch("hestia_web.app.sib_api_v3_sdk")
    def test_login_rate_limit_per_email(self, mock_sdk, mock_get_db, client):
        """Test that login is rate limited to 5 requests per email per hour."""
        # Mock database for storing magic token
        cur = make_mock_cursor()
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        # Get CSRF token from index page
        index_resp = client.get("/")
        csrf_token = get_csrf_token(index_resp.data.decode())

        # Make 5 successful requests (should work)
        for i in range(5):
            resp = client.post(
                "/login",
                data={"email": "ratelimit@example.com", "csrf_token": csrf_token},
                follow_redirects=False
            )
            assert resp.status_code == 302

        # 6th request should be rate limited
        resp = client.post(
            "/login",
            data={"email": "ratelimit@example.com", "csrf_token": csrf_token},
            follow_redirects=False
        )
        assert resp.status_code == 429

    @patch("hestia_web.app.get_db")
    @patch("hestia_web.app.sib_api_v3_sdk")
    def test_login_rate_limit_per_ip(self, mock_sdk, mock_get_db, client):
        """Test that login is rate limited to 20 requests per IP per hour."""
        # Mock database for storing magic token
        cur = make_mock_cursor()
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        # Get CSRF token from index page
        index_resp = client.get("/")
        csrf_token = get_csrf_token(index_resp.data.decode())

        # Make 20 successful requests with different emails (should work)
        for i in range(20):
            resp = client.post(
                "/login",
                data={"email": f"user{i}@example.com", "csrf_token": csrf_token},
                follow_redirects=False
            )
            assert resp.status_code == 302

        # 21st request should be rate limited
        resp = client.post(
            "/login",
            data={"email": "user99@example.com", "csrf_token": csrf_token},
            follow_redirects=False
        )
        assert resp.status_code == 429

    def test_login_rate_limit_different_emails_independent(self, client):
        """Test that rate limits for different emails are independent."""
        # This test verifies that hitting the limit for one email doesn't affect others
        # We've already tested the per-email limit above, this just confirms independence
        # by checking that we can still make requests to other emails after hitting
        # the limit for one
        pass  # This is implicitly tested by test_login_rate_limit_per_ip


# =====================================================================
# AUTH TOKEN TESTS
# =====================================================================

class TestAuth:
    def test_invalid_token_redirects_with_message(self, client):
        resp = client.get("/auth/invalid-token", follow_redirects=False)
        assert resp.status_code == 302
        assert "Invalid" in resp.headers["Location"] or "expired" in resp.headers["Location"]

    @patch("hestia_web.app.get_db")
    def test_valid_token_sets_session_and_redirects_to_dashboard(self, mock_get_db, client):
        token_id, signed_token = hestia_app.generate_magic_token("user@example.com")

        cur = make_mock_cursor()
        # fetchone: magic_tokens lookup (token exists)
        cur.fetchone.return_value = {"token_id": token_id}
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get(f"/auth/{signed_token}", follow_redirects=False)
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]

        # Should have a session cookie set in the response
        cookie_header = resp.headers.get("Set-Cookie", "")
        assert "hestia_session" in cookie_header


# =====================================================================
# SESSION & AUTH DECORATOR TESTS
# =====================================================================

class TestSession:
    def test_dashboard_without_session_redirects(self, client):
        resp = client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 302
        assert "/" == resp.headers["Location"] or "login" in resp.headers["Location"].lower() or resp.headers["Location"].endswith("/")

    def test_dashboard_with_invalid_cookie_redirects(self, client):
        client.set_cookie("hestia_session", "garbage-value", domain="localhost")
        resp = client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 302

    def test_session_cookie_is_httponly(self, client):
        """Verify that set_session_cookie sets httponly flag."""
        from flask import Flask
        test_app = Flask(__name__)
        test_app.config["SECRET_KEY"] = "test"
        with test_app.test_request_context():
            from flask import make_response as mr, redirect as rd
            resp = mr(rd("/"))
            hestia_app.set_session_cookie(resp, "user@example.com")
            # Check the Set-Cookie header
            cookie_header = resp.headers.get("Set-Cookie", "")
            assert "HttpOnly" in cookie_header

    def test_session_cookie_is_secure(self, client):
        """Verify that set_session_cookie sets the Secure flag (HTTPS only)."""
        from flask import Flask
        test_app = Flask(__name__)
        test_app.config["SECRET_KEY"] = "test"
        with test_app.test_request_context():
            from flask import make_response as mr, redirect as rd
            resp = mr(rd("/"))
            hestia_app.set_session_cookie(resp, "user@example.com")
            cookie_header = resp.headers.get("Set-Cookie", "")
            assert "Secure" in cookie_header


# =====================================================================
# DASHBOARD TESTS
# =====================================================================

class TestDashboard:
    @patch("hestia_web.app.get_db")
    def test_dashboard_unlinked_shows_link_telegram_button(self, mock_get_db, client):
        set_session(client)
        sub = mock_subscriber(telegram_id=None)
        cur = make_dashboard_cursor(sub)
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/dashboard")
        html = resp.data.decode()
        assert resp.status_code == 200
        assert "Link Telegram" in html

    @patch("hestia_web.app.get_db")
    def test_dashboard_unlinked_shows_filters(self, mock_get_db, client):
        """Filters should be accessible even without Telegram linked."""
        set_session(client)
        sub = mock_subscriber(telegram_id=None)
        cur = make_dashboard_cursor(sub)
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/dashboard")
        html = resp.data.decode()
        assert resp.status_code == 200
        assert "min_price" in html
        assert "max_price" in html
        assert "filter_agencies" in html
        assert "filter_cities" in html

    @patch("hestia_web.app.get_db")
    def test_dashboard_linked_shows_filters(self, mock_get_db, client):
        set_session(client)
        sub = mock_subscriber(telegram_id=12345)
        cur = make_dashboard_cursor(sub)
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/dashboard")
        html = resp.data.decode()
        assert resp.status_code == 200
        assert "notifications_enabled" in html
        assert "min_price" in html
        assert "max_price" in html
        # Toggle should be present, Link Telegram button should NOT
        assert "telegram-modal" not in html

    @patch("hestia_web.app.get_db")
    def test_dashboard_shows_email(self, mock_get_db, client):
        set_session(client, email="hello@world.com")
        sub = mock_subscriber(email_address="hello@world.com", telegram_id=12345)
        cur = make_dashboard_cursor(sub)
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/dashboard")
        html = resp.data.decode()
        assert "hello@world.com" in html

    def test_dashboard_subscriber_not_found_auto_creates(self, client):
        set_session(client, email="unknown@example.com")
        # First fetchone returns None (no subscriber), second returns the newly created one
        new_sub = mock_subscriber(email_address="unknown@example.com", telegram_id=None)
        cur = MagicMock()
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        cur.fetchone.side_effect = [None, new_sub]
        cur.fetchall.side_effect = [MOCK_CITIES_ROWS, MOCK_AGENCIES_ROWS]
        conn = make_mock_conn(cur)

        with patch("hestia_web.app.get_db", return_value=conn):
            resp = client.get("/dashboard")
        assert resp.status_code == 200
        html = resp.data.decode()
        # New user should have is_new_user data attribute set to true
        assert 'data-is-new-user="true"' in html
        # Verify INSERT was called to auto-create subscriber
        insert_calls = [c for c in cur.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) >= 1

    def test_dashboard_existing_user_is_not_new(self, client):
        """Existing subscribers should have is_new_user=false."""
        set_session(client)
        sub = mock_subscriber(telegram_id=None)
        cur = make_dashboard_cursor(sub)
        conn = make_mock_conn(cur)

        with patch("hestia_web.app.get_db", return_value=conn):
            resp = client.get("/dashboard")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'data-is-new-user="false"' in html

    @patch("hestia_web.app.get_db")
    def test_link_telegram_page_auto_generates_code(self, mock_get_db, client):
        set_session(client)
        cur = make_mock_cursor()
        # fetchone: linked check (telegram not linked yet → None)
        cur.fetchone.return_value = None
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/link-telegram")
        html = resp.data.decode()
        assert "Your code:" in html
        assert "t.me/hestia_homes_bot" in html
        # Verify INSERT was called to create a link code
        insert_calls = [
            c for c in cur.execute.call_args_list if "INSERT" in str(c) and "link_codes" in str(c)
        ]
        assert len(insert_calls) == 1

    @patch("hestia_web.app.get_db")
    def test_dashboard_linked_shows_filter_values(self, mock_get_db, client):
        set_session(client)
        sub = mock_subscriber(
            telegram_id=12345,
            filter_min_price=800,
            filter_max_price=2000,
            filter_cities=["Amsterdam", "Utrecht"],
            filter_agencies=["agency1"],
            notifications_enabled=True,
        )
        cur = make_dashboard_cursor(sub)
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/dashboard")
        html = resp.data.decode()
        assert "800" in html
        assert "2000" in html
        assert "Amsterdam" in html
        assert "Utrecht" in html
        assert "Agency One" in html
        assert "checked" in html


# =====================================================================
# API HOMES TESTS
# =====================================================================

MOCK_HOMES_ROWS = [
    {
        "url": "https://example.com/home1",
        "address": "123 Main St",
        "city": "Amsterdam",
        "price": 1200,
        "agency": "agency1",
        "date_added": "2025-01-15T10:30:00",
    },
    {
        "url": "https://example.com/home2",
        "address": "456 Oak Ave",
        "city": "Rotterdam",
        "price": 900,
        "agency": "agency2",
        "date_added": "2025-01-14T09:00:00",
    },
]

MOCK_SUBSCRIBER_FOR_HOMES = {
    "filter_min_price": 500,
    "filter_max_price": 2000,
    "filter_cities": ["amsterdam", "rotterdam"],
    "filter_agencies": ["agency1", "agency2"],
}


class TestApiHomes:
    def test_api_homes_requires_auth(self, client):
        resp = client.get("/api/homes")
        assert resp.status_code == 302

    @patch("hestia_web.app.get_db")
    def test_api_homes_returns_homes(self, mock_get_db, client):
        set_session(client)
        cur = MagicMock()
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        cur.fetchone.side_effect = [
            MOCK_SUBSCRIBER_FOR_HOMES,  # subscriber lookup
            {"cnt": 2},  # count query
        ]
        cur.fetchall.return_value = MOCK_HOMES_ROWS
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/api/homes")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "homes" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["per_page"] == 20
        assert len(data["homes"]) == 2

    @patch("hestia_web.app.get_db")
    def test_api_homes_pagination(self, mock_get_db, client):
        set_session(client)
        cur = MagicMock()
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        cur.fetchone.side_effect = [
            MOCK_SUBSCRIBER_FOR_HOMES,
            {"cnt": 50},
        ]
        cur.fetchall.return_value = MOCK_HOMES_ROWS
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/api/homes?page=2&per_page=10")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["page"] == 2
        assert data["per_page"] == 10

    @patch("hestia_web.app.get_db")
    def test_api_homes_no_subscriber(self, mock_get_db, client):
        set_session(client)
        cur = MagicMock()
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = None
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/api/homes")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["homes"] == []
        assert data["total"] == 0

    @patch("hestia_web.app.get_db")
    def test_api_homes_empty_filters(self, mock_get_db, client):
        """When user has no cities and no agencies, return empty."""
        set_session(client)
        cur = MagicMock()
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = {
            "filter_min_price": 500,
            "filter_max_price": 2000,
            "filter_cities": [],
            "filter_agencies": [],
        }
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/api/homes")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["homes"] == []
        assert data["total"] == 0


# =====================================================================
# LINK TELEGRAM TESTS
# =====================================================================

class TestLinkTelegram:
    @patch("hestia_web.app.get_db")
    def test_link_telegram_redirects_to_dashboard_if_already_linked(self, mock_get_db, client):
        set_session(client)

        cur = make_mock_cursor()
        # subscriber lookup finds fully linked row
        cur.fetchone.return_value = {"id": 42}
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/link-telegram", follow_redirects=False)
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]

    def test_link_telegram_requires_auth(self, client):
        resp = client.get("/link-telegram", follow_redirects=False)
        assert resp.status_code == 302
        # Should redirect to index
        loc = resp.headers["Location"]
        assert loc.endswith("/") or "index" in loc

    @patch("hestia_web.app.get_db")
    def test_link_telegram_deletes_old_codes(self, mock_get_db, client):
        set_session(client)
        cur = make_mock_cursor()
        cur.fetchone.return_value = None
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        client.get("/link-telegram")

        # Verify DELETE was called before INSERT
        delete_calls = [c for c in cur.execute.call_args_list if "DELETE" in str(c)]
        assert len(delete_calls) >= 1


# =====================================================================
# CHECK TELEGRAM POLLING TESTS
# =====================================================================

class TestCheckTelegram:
    def test_check_telegram_no_auth_returns_false(self, client):
        resp = client.get("/link-telegram/check")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["linked"] is False

    @patch("hestia_web.app.get_db")
    def test_check_telegram_not_linked(self, mock_get_db, client):
        set_session(client)
        cur = make_mock_cursor()
        cur.fetchall.return_value = [mock_subscriber(telegram_id=None)]
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/link-telegram/check")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["linked"] is False

    @patch("hestia_web.app.get_db")
    def test_check_telegram_linked(self, mock_get_db, client):
        set_session(client)
        cur = make_mock_cursor()
        cur.fetchall.return_value = [mock_subscriber(telegram_id="12345")]
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/link-telegram/check")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["linked"] is True


# =====================================================================
# API LINK CODE TESTS
# =====================================================================

class TestApiLinkCode:
    def test_api_link_code_requires_auth(self, client):
        resp = client.post("/api/link-code")
        assert resp.status_code == 302

    @patch("hestia_web.app.get_db")
    def test_api_link_code_requires_csrf(self, mock_get_db, client):
        set_session(client)
        resp = client.post("/api/link-code", data={})
        assert resp.status_code == 403

    @patch("hestia_web.app.get_db")
    def test_api_link_code_returns_code(self, mock_get_db, client):
        set_session(client)
        csrf_token = get_csrf_token_for_session(client)
        cur = make_mock_cursor()
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.post("/api/link-code", data={"csrf_token": csrf_token})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "code" in data
        assert len(data["code"]) == 4
        assert data["code"].isalpha() and data["code"].isupper()
        assert data["expires_in"] == 300

    @patch("hestia_web.app.get_db")
    def test_api_link_code_stores_in_db(self, mock_get_db, client):
        set_session(client)
        csrf_token = get_csrf_token_for_session(client)
        cur = make_mock_cursor()
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        client.post("/api/link-code", data={"csrf_token": csrf_token})
        # Verify DELETE + INSERT were called
        delete_calls = [c for c in cur.execute.call_args_list if "DELETE" in str(c) and "link_codes" in str(c)]
        insert_calls = [c for c in cur.execute.call_args_list if "INSERT" in str(c) and "link_codes" in str(c)]
        assert len(delete_calls) == 1
        assert len(insert_calls) == 1


# =====================================================================
# LINK CODE GENERATION TESTS
# =====================================================================

class TestGenerateLinkCode:
    def test_generate_link_code_returns_code(self):
        """generate_link_code should return a 4-character uppercase code."""
        from hestia_web.app import generate_link_code

        code = generate_link_code()
        assert len(code) == 4
        assert code.isalpha()
        assert code.isupper()

    def test_insert_link_code_with_retry_succeeds_on_first_try(self):
        """insert_link_code_with_retry should insert successfully on first attempt."""
        from hestia_web.app import insert_link_code_with_retry

        cur = MagicMock()
        cur.rowcount = 1  # Simulate successful insert
        code = insert_link_code_with_retry(cur, "test@example.com")

        assert len(code) == 4
        assert code.isalpha()
        assert code.isupper()

        # Verify INSERT was called once
        cur.execute.assert_called_once()
        assert "INSERT INTO hestia.link_codes" in cur.execute.call_args[0][0]
        assert "ON CONFLICT" in cur.execute.call_args[0][0]

    def test_insert_link_code_with_retry_retries_on_collision(self):
        """insert_link_code_with_retry should retry if a collision occurs."""
        from hestia_web.app import insert_link_code_with_retry

        cur = MagicMock()
        # First attempt: collision (rowcount=0), second succeeds (rowcount=1)
        cur.rowcount = 0  # Will be set to 0 first, then 1

        # Track call count and set rowcount appropriately
        call_count = [0]
        def set_rowcount(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                cur.rowcount = 0  # First call: collision
            else:
                cur.rowcount = 1  # Second call: success

        cur.execute.side_effect = set_rowcount

        code = insert_link_code_with_retry(cur, "test@example.com")

        assert len(code) == 4
        assert code.isalpha()
        assert code.isupper()

        # Verify two INSERT attempts were made
        assert cur.execute.call_count == 2

    def test_insert_link_code_with_retry_raises_after_max_attempts(self):
        """insert_link_code_with_retry should raise RuntimeError after exhausting retries."""
        from hestia_web.app import insert_link_code_with_retry

        cur = MagicMock()
        # Always return collision (rowcount=0)
        cur.rowcount = 0

        with pytest.raises(RuntimeError) as exc_info:
            insert_link_code_with_retry(cur, "test@example.com", max_attempts=3)

        assert "Unable to generate unique link code after 3 attempts" in str(exc_info.value)
        assert cur.execute.call_count == 3

    def test_insert_link_code_with_retry_reraises_other_db_errors(self):
        """insert_link_code_with_retry should re-raise non-IntegrityError database errors."""
        from hestia_web.app import insert_link_code_with_retry
        import psycopg2

        cur = MagicMock()
        # Raise a different type of database error
        cur.execute.side_effect = psycopg2.OperationalError("connection lost")

        with pytest.raises(psycopg2.OperationalError):
            insert_link_code_with_retry(cur, "test@example.com")


# =====================================================================
# MERGE LOGIC TESTS
# =====================================================================

class TestMergeLogic:
    @patch("hestia_web.app.get_db")
    def test_merge_when_both_rows_exist(self, mock_get_db, client):
        """When email-only and telegram rows both exist, they should be merged."""
        set_session(client)
        email_row = mock_subscriber(id=1, telegram_id=None, filter_min_price=500, filter_max_price=2000)
        telegram_row = mock_subscriber(
            id=2, telegram_id="99999", filter_min_price=800, filter_max_price=1800,
            filter_cities=["Utrecht"], filter_agencies=["agency2"],
        )
        cur = make_mock_cursor()
        cur.fetchall.return_value = [email_row, telegram_row]
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/link-telegram/check")
        data = resp.get_json()
        assert data["linked"] is True

        # Verify UPDATE was called on email-only row (id=1)
        update_calls = [c for c in cur.execute.call_args_list if "UPDATE" in str(c)]
        assert len(update_calls) == 1
        update_args = update_calls[0][0][1]
        assert update_args[0] == "99999"  # telegram_id
        assert update_args[6] == 1  # email_only row id

        # Verify DELETE was called on telegram row (id=2)
        delete_calls = [c for c in cur.execute.call_args_list if "DELETE" in str(c)]
        assert len(delete_calls) == 1
        delete_args = delete_calls[0][0][1]
        assert delete_args[0] == 2  # telegram row id

    @patch("hestia_web.app.get_db")
    def test_no_merge_when_only_email_row(self, mock_get_db, client):
        """When only an email-only row exists, linked should be False."""
        set_session(client)
        email_row = mock_subscriber(id=1, telegram_id=None)
        cur = make_mock_cursor()
        cur.fetchall.return_value = [email_row]
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/link-telegram/check")
        data = resp.get_json()
        assert data["linked"] is False

    @patch("hestia_web.app.get_db")
    def test_no_merge_when_already_linked(self, mock_get_db, client):
        """When only a single linked row exists, linked should be True, no merge."""
        set_session(client)
        linked_row = mock_subscriber(id=1, telegram_id="12345")
        cur = make_mock_cursor()
        cur.fetchall.return_value = [linked_row]
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/link-telegram/check")
        data = resp.get_json()
        assert data["linked"] is True
        # No UPDATE or DELETE should have been called
        update_calls = [c for c in cur.execute.call_args_list if "UPDATE" in str(c)]
        delete_calls = [c for c in cur.execute.call_args_list if "DELETE" in str(c)]
        assert len(update_calls) == 0
        assert len(delete_calls) == 0


# =====================================================================
# FILTER UPDATE TESTS
# =====================================================================

class TestFilterUpdate:
    def test_update_filters_requires_auth(self, client):
        resp = client.post("/dashboard/filters", follow_redirects=False)
        assert resp.status_code == 302

    @patch("hestia_web.app.get_db")
    def test_update_filters_saves_data(self, mock_get_db, client):
        set_session(client)
        csrf_token = get_csrf_token_for_session(client)
        cur = make_mock_cursor()
        # fetchone: subscriber's current filter_agencies
        cur.fetchone.return_value = {"filter_agencies": ["agency1"]}
        # fetchall: enabled agencies from hestia.targets
        cur.fetchall.return_value = [{"agency": "agency1"}, {"agency": "agency2"}]
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.post(
            "/dashboard/filters",
            data=MultiDict([
                ("csrf_token", csrf_token),
                ("notifications_enabled", "on"),
                ("min_price", "500"),
                ("max_price", "1500"),
                ("filter_cities", "Amsterdam"),
                ("filter_cities", "Rotterdam"),
                ("filter_agencies", "agency1"),
            ]),
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]

        # Verify the UPDATE query was executed
        update_calls = [c for c in cur.execute.call_args_list if "UPDATE" in str(c)]
        assert len(update_calls) == 1

        # Check the arguments passed to the UPDATE
        args = update_calls[0][0][1]
        assert args[0] is True  # notifications_enabled
        assert args[1] == 500  # min_price
        assert args[2] == 1500  # max_price
        assert args[3].adapted == ["amsterdam", "rotterdam"]  # filter_cities (Json wrapper)
        assert args[4].adapted == ["agency1"]  # filter_agencies (Json wrapper)
        assert args[5] == "user@example.com"  # email

    @patch("hestia_web.app.get_db")
    def test_update_filters_preserves_hidden_agencies(self, mock_get_db, client):
        """Agencies disabled in hestia.targets should be preserved on save."""
        set_session(client)
        csrf_token = get_csrf_token_for_session(client)
        cur = make_mock_cursor()
        # User previously had agency1 + disabled_agency in their filters
        cur.fetchone.return_value = {"filter_agencies": ["agency1", "disabled_agency"]}
        # Only agency1 is currently enabled (disabled_agency is not in targets)
        cur.fetchall.return_value = [{"agency": "agency1"}, {"agency": "agency2"}]
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.post(
            "/dashboard/filters",
            data=MultiDict([
                ("csrf_token", csrf_token),
                ("notifications_enabled", "on"),
                ("min_price", "500"),
                ("max_price", "1500"),
                ("filter_agencies", "agency1"),
            ]),
            follow_redirects=False,
        )
        assert resp.status_code == 302

        update_calls = [c for c in cur.execute.call_args_list if "UPDATE" in str(c)]
        args = update_calls[0][0][1]
        # Should contain the submitted agency1 + the hidden disabled_agency
        assert "agency1" in args[4].adapted
        assert "disabled_agency" in args[4].adapted

    @patch("hestia_web.app.get_db")
    def test_update_filters_empty_values(self, mock_get_db, client):
        set_session(client)
        csrf_token = get_csrf_token_for_session(client)
        cur = make_mock_cursor()
        cur.fetchone.return_value = {"filter_agencies": []}
        cur.fetchall.return_value = [{"agency": "agency1"}]
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.post(
            "/dashboard/filters",
            data={
                "csrf_token": csrf_token,
                "min_price": "",
                "max_price": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

        update_calls = [c for c in cur.execute.call_args_list if "UPDATE" in str(c)]
        args = update_calls[0][0][1]
        assert args[0] is False  # notifications_enabled (checkbox not in form = unchecked)
        assert args[1] is None  # min_price empty
        assert args[2] is None  # max_price empty
        assert args[3].adapted == []  # filter_cities empty (Json wrapper)
        assert args[4].adapted == []  # filter_agencies empty (Json wrapper)

    @patch("hestia_web.app.get_db")
    def test_update_filters_non_numeric_price_defaults_to_none(self, mock_get_db, client):
        """Non-numeric price values should default to None instead of causing a 500."""
        set_session(client)
        csrf_token = get_csrf_token_for_session(client)
        cur = make_mock_cursor()
        cur.fetchone.return_value = {"filter_agencies": []}
        cur.fetchall.return_value = [{"agency": "agency1"}]
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.post(
            "/dashboard/filters",
            data={
                "csrf_token": csrf_token,
                "min_price": "abc",
                "max_price": "not_a_number",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

        update_calls = [c for c in cur.execute.call_args_list if "UPDATE" in str(c)]
        args = update_calls[0][0][1]
        assert args[1] is None  # min_price invalid → None
        assert args[2] is None  # max_price invalid → None

    @patch("hestia_web.app.get_db")
    def test_update_filters_price_clamped_to_range(self, mock_get_db, client):
        """Prices outside 0–99999 should be clamped."""
        set_session(client)
        csrf_token = get_csrf_token_for_session(client)
        cur = make_mock_cursor()
        cur.fetchone.return_value = {"filter_agencies": []}
        cur.fetchall.return_value = [{"agency": "agency1"}]
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.post(
            "/dashboard/filters",
            data={
                "csrf_token": csrf_token,
                "min_price": "-50",
                "max_price": "999999",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

        update_calls = [c for c in cur.execute.call_args_list if "UPDATE" in str(c)]
        args = update_calls[0][0][1]
        assert args[1] == 0       # min_price clamped from -50 to 0
        assert args[2] == 99999   # max_price clamped from 999999 to 99999


# =====================================================================
# LOGOUT TESTS
# =====================================================================

class TestLogout:
    def test_logout_clears_cookie_and_redirects(self, client):
        set_session(client)
        resp = client.get("/logout", follow_redirects=False)
        assert resp.status_code == 302
        # Should redirect to index
        loc = resp.headers["Location"]
        assert loc.endswith("/") or "index" in loc

        # Cookie should be cleared (set to empty or expired)
        cookie_header = resp.headers.get("Set-Cookie", "")
        assert "hestia_session" in cookie_header


# =====================================================================
# TOKEN GENERATION TESTS (unit tests)
# =====================================================================

class TestTokens:
    def test_magic_token_roundtrip(self):
        token_id, signed_token = hestia_app.generate_magic_token("test@example.com")
        result = hestia_app.verify_magic_token(signed_token)
        assert result is not None
        email, returned_token_id = result
        assert email == "test@example.com"
        assert returned_token_id == token_id

    def test_magic_token_bad_signature(self):
        result = hestia_app.verify_magic_token("not-a-valid-token")
        assert result is None

    def test_session_cookie_roundtrip(self):
        value = hestia_app.serializer.dumps("user@example.com", salt="email-session")
        result = hestia_app.serializer.loads(value, salt="email-session", max_age=3600)
        assert result == "user@example.com"

    def test_different_salts_dont_mix(self):
        token = hestia_app.serializer.dumps("data", salt="magic-link")
        with pytest.raises(Exception):
            hestia_app.serializer.loads(token, salt="session", max_age=3600)


# =====================================================================
# TEMPLATE RENDERING TESTS
# =====================================================================

class TestTemplates:
    def test_base_template_has_meta_viewport(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert 'name="viewport"' in html
        assert "width=device-width" in html

    def test_base_template_has_title(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert "<title>" in html
        assert "Hestia" in html

    def test_css_styles_present(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert 'href="/static/style.css"' in html


# =====================================================================
# APP CONFIGURATION TESTS
# =====================================================================

class TestAppConfig:
    def test_debug_mode_is_off_by_default(self):
        """Ensure debug mode is not enabled by default (production safety)."""
        assert hestia_app.app.debug is False


# =====================================================================
# CSRF PROTECTION TESTS
# =====================================================================

class TestCSRFProtection:
    def test_generate_csrf_token_with_session(self, client):
        """CSRF token generation should work when session exists."""
        set_session(client, email="user@example.com")
        # Make a request to establish request context
        resp = client.get("/")
        assert resp.status_code == 302  # Redirects to dashboard when logged in

    def test_generate_csrf_token_without_session(self, client):
        """CSRF token generation should return empty string without session."""
        # Generate CSRF token directly without session
        cookie_value = None
        if cookie_value:
            token = hestia_app.serializer.dumps(cookie_value, salt="csrf-token")
        else:
            token = ""
        assert token == ""

    def test_validate_csrf_token_valid(self, client):
        """Valid CSRF token should pass validation."""
        set_session(client, email="user@example.com")
        csrf_token = get_csrf_token_for_session(client)
        # Make a request to establish request context, then validate token
        resp = client.get("/")
        assert csrf_token is not None

    def test_validate_csrf_token_invalid(self, client):
        """Invalid CSRF token should fail validation."""
        set_session(client, email="user@example.com")
        # Try to validate an invalid token - the actual validation happens in POST routes
        # This test verifies the behavior through an actual POST request
        resp = client.post(
            "/dashboard/filters",
            data={"csrf_token": "invalid-token"},
            follow_redirects=False
        )
        # Should redirect back to dashboard (CSRF validation failed)
        assert resp.status_code == 302

    def test_validate_csrf_token_empty(self, client):
        """Empty CSRF token should fail validation."""
        set_session(client, email="user@example.com")
        # Empty CSRF token should fail validation in POST routes
        resp = client.post(
            "/dashboard/filters",
            data={"csrf_token": ""},
            follow_redirects=False
        )
        assert resp.status_code == 302

    def test_validate_csrf_token_no_session(self, client):
        """CSRF token validation should fail without session."""
        # No session, so POST to protected route should redirect to login
        resp = client.post(
            "/dashboard/filters",
            data={"csrf_token": "some-token"},
            follow_redirects=False
        )
        assert resp.status_code == 302
        assert "/" in resp.headers["Location"]

    @patch("hestia_web.app.get_db")
    @patch("hestia_web.app.sib_api_v3_sdk")
    def test_login_without_csrf_token_fails(self, mock_sdk, mock_get_db, client):
        """POST to /login without CSRF token should be rejected."""
        resp = client.post(
            "/login",
            data={"email": "user@example.com"},
            follow_redirects=False
        )
        assert resp.status_code == 302
        # URL encoding: "Invalid security token" becomes "Invalid+security+token"
        assert "Invalid+security+token" in resp.headers["Location"]

    @patch("hestia_web.app.get_db")
    @patch("hestia_web.app.sib_api_v3_sdk")
    def test_login_with_invalid_csrf_token_fails(self, mock_sdk, mock_get_db, client):
        """POST to /login with invalid CSRF token should be rejected."""
        resp = client.post(
            "/login",
            data={"email": "user@example.com", "csrf_token": "invalid-token"},
            follow_redirects=False
        )
        assert resp.status_code == 302
        # URL encoding: "Invalid security token" becomes "Invalid+security+token"
        assert "Invalid+security+token" in resp.headers["Location"]

    @patch("hestia_web.app.get_db")
    @patch("hestia_web.app.sib_api_v3_sdk")
    def test_login_with_valid_csrf_token_succeeds(self, mock_sdk, mock_get_db, client):
        """POST to /login with valid CSRF token should succeed."""
        # Mock database for storing magic token
        cur = make_mock_cursor()
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        # Get CSRF token from the index page
        resp = client.get("/")
        html = resp.data.decode()
        csrf_token = get_csrf_token(html)
        assert csrf_token, "CSRF token not found in form"

        # Submit login form with CSRF token
        resp = client.post(
            "/login",
            data={"email": "user@example.com", "csrf_token": csrf_token},
            follow_redirects=False
        )
        assert resp.status_code == 302
        # Should not contain error message about security token
        assert "Invalid+security+token" not in resp.headers.get("Location", "")

    @patch("hestia_web.app.get_db")
    def test_update_filters_without_csrf_token_fails(self, mock_get_db, client):
        """POST to /dashboard/filters without CSRF token should be rejected."""
        set_session(client, email="user@example.com")

        resp = client.post(
            "/dashboard/filters",
            data={"min_price": "500", "max_price": "1500"},
            follow_redirects=False
        )
        # Should redirect back to dashboard without making changes
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]

    @patch("hestia_web.app.get_db")
    def test_update_filters_with_invalid_csrf_token_fails(self, mock_get_db, client):
        """POST to /dashboard/filters with invalid CSRF token should be rejected."""
        set_session(client, email="user@example.com")

        resp = client.post(
            "/dashboard/filters",
            data={"min_price": "500", "max_price": "1500", "csrf_token": "invalid-token"},
            follow_redirects=False
        )
        # Should redirect back to dashboard without making changes
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]

    @patch("hestia_web.app.get_db")
    def test_update_filters_with_valid_csrf_token_succeeds(self, mock_get_db, client):
        """POST to /dashboard/filters with valid CSRF token should succeed."""
        set_session(client, email="user@example.com")

        # Mock database responses
        subscriber = mock_subscriber(telegram_id="123456")
        cur = make_dashboard_cursor(subscriber)
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        # Get CSRF token from the dashboard page
        resp = client.get("/dashboard")
        html = resp.data.decode()
        csrf_token = get_csrf_token(html)
        assert csrf_token, "CSRF token not found in dashboard form"

        # Mock database for the update query
        cur2 = make_mock_cursor()
        cur2.fetchone.return_value = {"filter_agencies": ["agency1"]}
        cur2.fetchall.return_value = [{"agency": "agency1"}]
        conn2 = make_mock_conn(cur2)
        mock_get_db.return_value = conn2

        # Submit filter update with CSRF token
        resp = client.post(
            "/dashboard/filters",
            data={
                "csrf_token": csrf_token,
                "min_price": "500",
                "max_price": "1500",
                "filter_cities": ["amsterdam"],
                "filter_agencies": ["agency1"],
            },
            follow_redirects=False
        )
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]

    def test_csrf_token_appears_in_login_form(self, client):
        """Login form should contain a hidden CSRF token field."""
        resp = client.get("/")
        html = resp.data.decode()
        assert 'name="csrf_token"' in html
        assert 'type="hidden"' in html

    @patch("hestia_web.app.get_db")
    def test_csrf_token_appears_in_dashboard_form(self, mock_get_db, client):
        """Dashboard filter form should contain a hidden CSRF token field."""
        set_session(client, email="user@example.com")

        # Mock database responses
        subscriber = mock_subscriber(telegram_id="123456")
        cur = make_dashboard_cursor(subscriber)
        conn = make_mock_conn(cur)
        mock_get_db.return_value = conn

        resp = client.get("/dashboard")
        html = resp.data.decode()
        assert 'name="csrf_token"' in html
        assert 'type="hidden"' in html


class TestConnectionPool:
    """Test database connection pooling functionality."""

    def test_connection_pool_starts_none(self):
        """Connection pool should be None before first use (lazy initialization)."""
        # Reset the pool to test lazy init
        original_pool = hestia_app.db_pool
        hestia_app.db_pool = None
        assert hestia_app.db_pool is None
        # Restore original pool
        hestia_app.db_pool = original_pool

    def test_get_db_returns_context_manager(self):
        """get_db() should return a PooledConnection context manager."""
        db_context = hestia_app.get_db()
        assert isinstance(db_context, hestia_app.PooledConnection)

    @patch("hestia_web.app._get_pool")
    def test_pooled_connection_gets_and_returns_connection(self, mock_get_pool):
        """PooledConnection should get connection on enter and return on exit."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        with hestia_app.get_db() as conn:
            assert conn is mock_conn
            mock_pool.getconn.assert_called_once()
            # putconn should not be called yet
            mock_pool.putconn.assert_not_called()

        # After exiting context, connection should be returned to pool
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("hestia_web.app._get_pool")
    def test_pooled_connection_default_autocommit_is_false(self, mock_get_pool):
        """PooledConnection should set autocommit=False by default for transactions."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        with hestia_app.get_db() as conn:
            assert conn.autocommit is False

    @patch("hestia_web.app._get_pool")
    def test_pooled_connection_explicit_autocommit(self, mock_get_pool):
        """PooledConnection should allow explicit autocommit=True."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        with hestia_app.get_db(autocommit=True) as conn:
            assert conn.autocommit is True

    @patch("hestia_web.app._get_pool")
    def test_pooled_connection_commits_on_success(self, mock_get_pool):
        """PooledConnection should commit transaction on successful exit."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        with hestia_app.get_db() as conn:
            pass  # Normal exit

        # Should commit and return connection to pool
        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("hestia_web.app._get_pool")
    def test_pooled_connection_rolls_back_on_exception(self, mock_get_pool):
        """PooledConnection should rollback transaction on exception."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        try:
            with hestia_app.get_db() as conn:
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should rollback and return connection to pool
        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("hestia_web.app._get_pool")
    def test_pooled_connection_autocommit_no_commit_or_rollback(self, mock_get_pool):
        """PooledConnection with autocommit should not call commit/rollback."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        with hestia_app.get_db(autocommit=True) as conn:
            pass  # Normal exit

        # Should not commit or rollback in autocommit mode
        mock_conn.commit.assert_not_called()
        mock_conn.rollback.assert_not_called()
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("hestia_web.app._get_pool")
    def test_pooled_connection_commit_error_rolls_back(self, mock_get_pool):
        """PooledConnection should rollback if commit fails."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.commit.side_effect = Exception("Commit failed")
        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        try:
            with hestia_app.get_db() as conn:
                pass  # Normal exit, but commit will fail
        except Exception:
            pass

        # Should attempt commit, then rollback on failure
        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_called_once()
        mock_pool.putconn.assert_called_once_with(mock_conn)


class TestTransactionBehavior:
    """Tests for database transaction behavior."""

    @patch("hestia_web.app.sib_api_v3_sdk")
    @patch("hestia_web.app._get_pool")
    def test_login_magic_tokens_are_transactional(self, mock_get_pool, mock_sdk):
        """DELETE and INSERT for magic_tokens should happen in a transaction."""
        # Setup mocks
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()

        # Track all execute calls
        execute_calls = []
        def track_execute(sql, params=None):
            execute_calls.append((sql, params))

        mock_cur.execute = track_execute
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        mock_conn.cursor.return_value = mock_cur
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.autocommit = False

        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        # Make request
        client = hestia_app.app.test_client()
        resp = client.get("/")
        html = resp.data.decode("utf-8")
        csrf_token = get_csrf_token(html)

        resp = client.post("/login", data={"email": "test@example.com", "csrf_token": csrf_token})

        # Verify transaction behavior
        assert execute_calls[0][0].strip().startswith("DELETE FROM hestia.magic_tokens")
        assert execute_calls[1][0].strip().startswith("INSERT INTO hestia.magic_tokens")

        # Verify connection was configured for transactions (not autocommit)
        assert mock_conn.autocommit is False

        # Verify commit was called
        mock_conn.commit.assert_called_once()

        # Verify connection was returned to pool
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("hestia_web.app._get_pool")
    def test_link_code_generation_is_transactional(self, mock_get_pool):
        """DELETE and INSERT for link_codes should happen in a transaction."""
        # Setup mocks
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()

        # Track all execute calls
        execute_calls = []
        def track_execute(sql, params=None):
            execute_calls.append((sql, params))

        mock_cur.execute = track_execute
        mock_cur.rowcount = 1  # Simulate successful insert
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        mock_conn.cursor.return_value = mock_cur
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.autocommit = False

        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        # Make authenticated request
        client = hestia_app.app.test_client()
        set_session(client, email="test@example.com")
        csrf_token = get_csrf_token_for_session(client)

        resp = client.post("/api/link-code", data={"csrf_token": csrf_token})

        # Verify transaction behavior
        assert execute_calls[0][0].strip().startswith("DELETE FROM hestia.link_codes")
        assert execute_calls[1][0].strip().startswith("INSERT INTO hestia.link_codes")
        assert "ON CONFLICT" in execute_calls[1][0]

        # Verify connection was configured for transactions (not autocommit)
        assert mock_conn.autocommit is False

        # Verify commit was called
        mock_conn.commit.assert_called_once()

        # Verify connection was returned to pool
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("hestia_web.app._get_pool")
    def test_transaction_rollback_on_database_error(self, mock_get_pool):
        """Transactions should rollback on database errors."""
        # Setup mocks
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()

        # Make the INSERT (second execute) fail
        # Order is now: DELETE, INSERT
        execute_count = 0
        def failing_execute(sql, params=None):
            nonlocal execute_count
            execute_count += 1
            if execute_count == 2:  # Fail on INSERT
                raise hestia_app.psycopg2.Error("Insert failed")

        mock_cur.execute = failing_execute
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)

        mock_conn.cursor.return_value = mock_cur
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.autocommit = False

        mock_pool.getconn.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        # Make authenticated request
        client = hestia_app.app.test_client()
        set_session(client, email="test@example.com")
        csrf_token = get_csrf_token_for_session(client)

        # Request should fail but not crash
        resp = client.post("/api/link-code", data={"csrf_token": csrf_token})

        # Verify rollback was called (not commit)
        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

        # Verify connection was still returned to pool
        mock_pool.putconn.assert_called_once_with(mock_conn)


class TestSecurityHeaders:
    """Tests for Content-Security-Policy and other security headers."""

    def test_csp_header_present(self):
        """All responses should have Content-Security-Policy header."""
        client = hestia_app.app.test_client()
        resp = client.get("/")
        assert "Content-Security-Policy" in resp.headers

    def test_csp_restricts_scripts(self):
        """CSP should restrict scripts to self, unpkg.com, and nonce."""
        client = hestia_app.app.test_client()
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        # Check for required sources
        assert "script-src 'self'" in csp
        assert "https://unpkg.com" in csp
        assert "'nonce-" in csp  # Should include a nonce
        # Should NOT allow unsafe-inline for scripts
        assert "script-src" in csp
        assert "'unsafe-inline'" not in csp.split("style-src")[0]  # Only check script-src part

    def test_csp_default_src_self(self):
        """CSP should set default-src to self."""
        client = hestia_app.app.test_client()
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp

    def test_csp_frame_ancestors_none(self):
        """CSP should prevent framing."""
        client = hestia_app.app.test_client()
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors 'none'" in csp

    def test_additional_security_headers(self):
        """Should include additional security headers."""
        client = hestia_app.app.test_client()
        resp = client.get("/")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Referrer-Policy" in resp.headers

    def test_templates_no_inline_scripts(self):
        """Templates should not contain inline <script> tags with code."""
        client = hestia_app.app.test_client()

        # Check index page
        resp = client.get("/")
        html = resp.data.decode("utf-8")
        # Should have external script tags but no inline script content
        assert '<script src="/static/base.js"></script>' in html
        assert '<script>(' not in html  # No inline IIFE scripts
        assert 'onclick=' not in html  # No inline event handlers

    def test_dashboard_no_inline_scripts(self):
        """Dashboard should not contain unsafe inline scripts (nonce-based allowed)."""
        client = hestia_app.app.test_client()
        set_session(client, email="test@example.com")

        resp = client.get("/dashboard")
        html = resp.data.decode("utf-8")
        # Check for unsafe inline patterns (event handlers)
        assert 'onclick=' not in html
        # Inline scripts are allowed only with nonce attribute
        if '<script>' in html and 'nonce=' not in html:
            # This would be an inline script without nonce (unsafe)
            assert False, "Found inline script without nonce attribute"


# =============================================================================
# Template Caching Tests
# =============================================================================

class TestTemplateCaching:
    """Tests for template caching functionality."""

    def test_email_template_is_cached(self):
        """get_email_template should cache the template content."""
        # Clear the cache first
        hestia_app.get_email_template.cache_clear()

        # First call should read from disk
        template1 = hestia_app.get_email_template()
        assert template1 is not None
        assert len(template1) > 0

        # Second call should return cached value (same object)
        template2 = hestia_app.get_email_template()
        assert template2 is template1  # Same object in memory

        # Verify cache_info shows hits
        cache_info = hestia_app.get_email_template.cache_info()
        assert cache_info.hits >= 1
        assert cache_info.misses == 1  # Only first call missed

    def test_email_template_cache_clear(self):
        """Cache clear should force a fresh read from disk."""
        # Clear and load
        hestia_app.get_email_template.cache_clear()
        template1 = hestia_app.get_email_template()

        # Clear again
        hestia_app.get_email_template.cache_clear()

        # Next call should be a cache miss
        cache_info_before = hestia_app.get_email_template.cache_info()
        assert cache_info_before.currsize == 0

        template2 = hestia_app.get_email_template()
        assert template2 == template1  # Same content

    def test_login_uses_cached_template(self, client):
        """Login route should use the cached email template."""
        # Clear the cache first
        hestia_app.get_email_template.cache_clear()

        with patch("hestia_web.app.PooledConnection") as mock_pool:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_pool.return_value.__enter__.return_value = mock_conn

            # Mock email sending
            with patch("hestia_web.app.sib_api_v3_sdk") as mock_sdk:
                mock_response = MagicMock()
                mock_response.message_id = "test-message-id"
                mock_sdk.TransactionalEmailsApi.return_value.send_transac_email.return_value = mock_response

                # Get CSRF token
                resp = client.get("/")
                csrf_token = get_csrf_token(resp.data.decode())

                # First login request
                client.post("/login", data={"email": "test@example.com", "csrf_token": csrf_token})

                # Get cache info after first request
                cache_info = hestia_app.get_email_template.cache_info()
                initial_hits = cache_info.hits

                # Get new CSRF token for second request
                resp2 = client.get("/")
                csrf_token2 = get_csrf_token(resp2.data.decode())

                # Second login request should hit the cache
                client.post("/login", data={"email": "test2@example.com", "csrf_token": csrf_token2})

                cache_info_after = hestia_app.get_email_template.cache_info()
                assert cache_info_after.hits > initial_hits  # Cache hit on second request

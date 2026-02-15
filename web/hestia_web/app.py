import os
import string
import secrets
import re
import functools
import uuid
import atexit
import logging
import sys
import ipaddress
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
import psycopg2.pool
from flask import (
    Flask, request, redirect, url_for, make_response, render_template,
    send_from_directory, jsonify, render_template_string, g,
)
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from dotenv import load_dotenv
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from pythonjsonlogger import jsonlogger

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["DATABASE_URL"] = os.environ["DATABASE_URL"]
app.config["BREVO_API_KEY"] = os.environ["BREVO_API_KEY"]
app.config["FROM_EMAIL"] = os.environ["FROM_EMAIL"]
app.config["BASE_URL"] = os.environ["BASE_URL"]

MAGIC_LINK_MAX_AGE = 15 * 60  # 15 minutes

PREVIEW_CACHE_OK_TTL = timedelta(days=30)
PREVIEW_CACHE_EMPTY_TTL = timedelta(days=7)
PREVIEW_CACHE_ERROR_TTL = timedelta(hours=1)
PREVIEW_IMAGE_MAX_BYTES = 5 * 1024 * 1024

RECENT_LOGIN_WINDOW_SECONDS = 10
RECENT_LOGIN_REQUESTS = {}
RECENT_LOGIN_MAX_ENTRIES = 10000
SESSION_MAX_AGE = 365 * 24 * 60 * 60  # 1 year
SESSION_COOKIE_NAME = "hestia_session"

serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# Configure logging with INFO level and JSON format support
log_format = os.getenv("LOG_FORMAT", "plain")  # "json" for production, "plain" for dev
logger = logging.getLogger("hestia")
logger.setLevel(logging.INFO)

# Remove any existing handlers to avoid duplicates
logger.handlers.clear()

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)

if log_format == "json":
    # Structured JSON logging for production
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        timestamp=True,
    )
else:
    # Plain text logging for development
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

handler.setFormatter(formatter)
logger.addHandler(handler)

# Prevent propagation to root logger to avoid duplicate logs
logger.propagate = False

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

def get_login_key():
    """Get rate limit key for /login - uses email from form data."""
    email = request.form.get("email", "").strip().lower()
    if email:
        return f"email:{email}"
    # Fall back to IP address if no email provided
    return f"ip:{get_remote_address()}"

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# ---------------------------------------------------------------------------
# Database connection pool
# ---------------------------------------------------------------------------

# Connection pool is lazily initialized on first use
db_pool = None

def _get_pool():
    """Get or create the database connection pool."""
    global db_pool
    if db_pool is None:
        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=app.config["DATABASE_URL"],
            options="-c timezone=UTC",
        )
    return db_pool

class PooledConnection:
    """Context manager for database connections from the pool.

    By default, autocommit is disabled to support transactions.
    Use autocommit=True for single-statement operations where atomicity isn't needed.
    """
    def __init__(self, autocommit=False):
        self.pool = None
        self.conn = None
        self.autocommit = autocommit

    def __enter__(self):
        self.pool = _get_pool()
        self.conn = self.pool.getconn()
        self.conn.autocommit = self.autocommit
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn and self.pool:
            try:
                # If not in autocommit mode and no exception, commit the transaction
                if not self.autocommit and exc_type is None:
                    try:
                        self.conn.commit()
                    except Exception as e:
                        logger.error(
                            "Error committing transaction",
                            extra={"error": str(e), "error_type": type(e).__name__},
                        )
                        self.conn.rollback()
                        raise
                # If there was an exception and not in autocommit mode, rollback
                elif not self.autocommit and exc_type is not None:
                    self.conn.rollback()
            finally:
                # Always return connection to pool, even if commit/rollback fails
                self.pool.putconn(self.conn)
        return False

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db(autocommit=False):
    """Return a pooled database connection context manager.

    Args:
        autocommit: If True, each statement commits immediately.
                   If False (default), use transactions with explicit commit/rollback.
    """
    return PooledConnection(autocommit=autocommit)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def generate_magic_token(email: str) -> tuple[str, str]:
    """Create a single-use magic token and store it in the database.

    Returns:
        tuple: (token_id, signed_token) - token_id to store in DB, signed_token for URL
    """
    token_id = str(uuid.uuid4())
    # Sign both the email and token_id together to prevent tampering
    signed_token = serializer.dumps({"email": email, "token_id": token_id}, salt="magic-link")
    return token_id, signed_token


def verify_magic_token(token: str) -> tuple[str, str] | None:
    """Verify the signed token and return (email, token_id) if valid.

    Note: This only verifies the signature and expiry. Caller must check
    that the token hasn't been used by querying the database.

    Returns:
        tuple: (email, token_id) if valid, None otherwise
    """
    try:
        data = serializer.loads(token, salt="magic-link", max_age=MAGIC_LINK_MAX_AGE)
        return data["email"], data["token_id"]
    except (BadSignature, SignatureExpired, KeyError, TypeError):
        return None


def set_session_cookie(response, email: str):
    """Set a signed session cookie containing the user's email."""
    value = serializer.dumps(email, salt="email-session")
    response.set_cookie(
        SESSION_COOKIE_NAME,
        value,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="Lax",
    )
    return response


def get_current_email() -> str | None:
    """Read and verify the session cookie. Return email or None."""
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie:
        return None
    try:
        email = serializer.loads(cookie, salt="email-session", max_age=SESSION_MAX_AGE)
        if not isinstance(email, str):
            return None
        return email
    except (BadSignature, SignatureExpired):
        return None


def login_required(f):
    """Decorator that redirects unauthenticated users away."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        email = get_current_email()
        if email is None:
            return redirect(url_for("index"))
        request.email = email
        return f(*args, **kwargs)
    return decorated


def generate_csrf_token() -> str:
    """Generate a CSRF token.

    For authenticated users, token is derived from session cookie.
    For anonymous users, generates a time-limited token.
    """
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie:
        # Authenticated: derive from session cookie
        return serializer.dumps(cookie, salt="csrf-token")
    else:
        # Anonymous: generate time-limited token
        # Use a constant value + timestamp to allow validation without state
        return serializer.dumps("anonymous", salt="csrf-token")


def validate_csrf_token(token: str) -> bool:
    """Validate a CSRF token.

    For authenticated users, validates against session cookie.
    For anonymous users, validates time-limited token.
    """
    if not token:
        return False

    cookie = request.cookies.get(SESSION_COOKIE_NAME)

    try:
        # Try to decode the token (checks signature and expiry)
        decoded = serializer.loads(token, salt="csrf-token", max_age=SESSION_MAX_AGE)

        if cookie:
            # Authenticated: token must match session cookie
            return decoded == cookie
        else:
            # Anonymous: token must be the anonymous marker
            return decoded == "anonymous"
    except (BadSignature, SignatureExpired):
        return False


@functools.lru_cache(maxsize=1)
def get_email_template() -> str:
    """Load and cache the email login template.

    Returns:
        The raw email template content

    Note:
        Cached to avoid repeated disk I/O on every login request.
    """
    with open(os.path.join(app.static_folder, "email_login.html")) as f:
        return f.read()


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    """Basic email format validation to avoid obvious invalid input."""
    return bool(EMAIL_REGEX.match(email))


LINK_CODE_ALPHABET = "".join(ch for ch in string.ascii_uppercase if ch not in "AEIOU")


def generate_link_code() -> str:
    """Generate a random 4-character link code.

    Returns:
        A random 4-character uppercase code

    Note:
        Does not check for uniqueness - caller should handle collision detection
        at INSERT time via try-except on unique constraint violations.
    """
    return "".join(secrets.choice(LINK_CODE_ALPHABET) for _ in range(4))


def insert_link_code_with_retry(cursor, email: str, max_attempts: int = 10) -> str:
    """Insert a link code with collision detection via retry.

    Args:
        cursor: Database cursor to use for the operation
        email: Email address to associate with the code
        max_attempts: Maximum number of attempts to generate a unique code

    Returns:
        The successfully inserted link code

    Raises:
        RuntimeError: If unable to generate a unique code after max_attempts

    Note:
        Uses ON CONFLICT DO NOTHING to avoid transaction-aborting IntegrityErrors.
        Checks cursor.rowcount to detect collisions without breaking the transaction.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    for attempt in range(max_attempts):
        code = generate_link_code()

        cursor.execute(
            """INSERT INTO hestia.link_codes (code, email_address, expires_at)
               VALUES (%s, %s, %s)
               ON CONFLICT (code) DO NOTHING""",
            (code, email, expires_at),
        )

        # Check if the insert was successful (rowcount = 1) or conflicted (rowcount = 0)
        if cursor.rowcount == 1:
            # Success - return the code
            return code
        else:
            continue

    # If we've exhausted all attempts, raise an error
    raise RuntimeError(f"Unable to generate unique link code after {max_attempts} attempts")


@app.context_processor
def inject_csrf_token():
    """Make CSRF token available to all templates."""
    return {"csrf_token": generate_csrf_token}

# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------

@app.before_request
def generate_csp_nonce():
    """Generate a nonce for inline scripts (CSP)."""
    g.csp_nonce = secrets.token_urlsafe(16)


@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    # Content-Security-Policy: restrict script/style sources
    # - self: allow resources from same origin
    # - unpkg.com: allow Lucide icons CDN
    # - nonce: allow specific inline scripts with matching nonce attribute
    # - unsafe-inline for styles: allows inline styles in templates (consider removing in future)
    nonce = getattr(g, 'csp_nonce', None)
    csp_directives = [
        "default-src 'self'",
        f"script-src 'self' https://unpkg.com 'nonce-{nonce}'" if nonce else "script-src 'self' https://unpkg.com",
        "style-src 'self' 'unsafe-inline'",  # TODO: remove unsafe-inline by extracting inline styles
        "img-src 'self' data: https:",
        "font-src 'self'",
        "connect-src 'self' https:",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
    response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

    # Additional security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Landing page with email input form."""
    if get_current_email() is not None:
        return redirect(url_for("dashboard"))
    message = request.args.get("message")
    return render_template("index.html", title="Login", message=message, contact_only=True)


@app.route("/login", methods=["POST"])
@limiter.limit("5 per hour", key_func=get_login_key, error_message="Too many login attempts. Please try again later.")
@limiter.limit("20 per hour", error_message="Too many login attempts from this location. Please try again later.")
def login():
    """Send a magic link email to the provided address."""
    # Validate CSRF token
    csrf_token = request.form.get("csrf_token", "")
    if not validate_csrf_token(csrf_token):
        return redirect(url_for("index", message="Invalid security token. Please try again."))

    email = request.form.get("email", "").strip().lower()
    if not email:
        return redirect(url_for("index", message="Please enter an email address."))

    if not is_valid_email(email):
        return redirect(url_for("index", message="Please enter a valid email address."))

    # Double-click guard: only suppress if a login was requested in the last 10 seconds
    if not app.config.get("TESTING"):
        now = time.monotonic()
        _cleanup_recent_logins(now)
        last = RECENT_LOGIN_REQUESTS.get(email)
        if last is not None and (now - last) < RECENT_LOGIN_WINDOW_SECONDS:
            return redirect(url_for("login_sent", email=email))
        RECENT_LOGIN_REQUESTS[email] = now

    # Generate single-use token
    token_id, signed_token = generate_magic_token(email)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=MAGIC_LINK_MAX_AGE)
    link = f"{app.config['BASE_URL']}/auth/{signed_token}"

    # Store token in database for single-use validation
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Clean up expired tokens for this email
                cur.execute(
                    "DELETE FROM hestia.magic_tokens WHERE email_address = %s AND expires_at < %s",
                    (email, datetime.now(timezone.utc)),
                )
                # Store the new token
                cur.execute(
                    "INSERT INTO hestia.magic_tokens (token_id, email_address, expires_at) VALUES (%s, %s, %s)",
                    (token_id, email, expires_at),
                )
    except psycopg2.Error as e:
        logger.error(
            "Database error storing magic token",
            extra={
                "email": email,
                "error": str(e),
                "error_type": type(e).__name__,
                "remote_addr": get_remote_address(),
            },
            exc_info=True,
        )
        return redirect(url_for("index", message="An error occurred. Please try again."))

    # Render email template (cached) with autoescaping enabled
    email_html = render_template_string(get_email_template(), link=link, base_url=app.config["BASE_URL"])

    # Send email via Brevo
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = app.config["BREVO_API_KEY"]
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": email}],
        sender={"email": app.config["FROM_EMAIL"], "name": "Hestia"},
        subject="Your Hestia login link",
        html_content=email_html,
    )
    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
    except ApiException as e:
        RECENT_LOGIN_REQUESTS.pop(email, None)
        logger.warning(
            "Failed to send magic link email",
            extra={
                "email": email,
                "error": str(e),
                "error_type": type(e).__name__,
                "remote_addr": get_remote_address(),
            },
            exc_info=True,
        )
        return redirect(url_for("index", message="Failed to send email. Please try again."))

    return redirect(url_for("login_sent", email=email))


@app.route("/login-sent")
def login_sent():
    """Confirmation page after requesting a login link."""
    if get_current_email() is not None:
        return redirect(url_for("dashboard"))
    email = request.args.get("email", "").strip().lower()
    if not email:
        return redirect(url_for("index"))
    return render_template("login_sent.html", title="Login", email=email, contact_only=True)


@app.route("/auth/<token>")
def auth(token):
    """Validate magic link token and create session. Token is single-use only."""
    # Verify the signature and expiry
    result = verify_magic_token(token)
    if result is None:
        logger.warning(
            "Auth attempt with invalid or expired token",
            extra={"remote_addr": get_remote_address()},
        )
        return redirect(url_for("index", message="Invalid or expired link."))

    email, token_id = result

    # Atomically consume the token (DELETE ... RETURNING prevents double-use)
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """DELETE FROM hestia.magic_tokens
                       WHERE token_id = %s AND email_address = %s AND expires_at > %s
                       RETURNING token_id""",
                    (token_id, email, datetime.now(timezone.utc)),
                )
                token_row = cur.fetchone()

                if token_row is None:
                    # Token doesn't exist or already used
                    logger.warning(
                        "Auth attempt with used or non-existent token",
                        extra={"email": email, "token_id": token_id, "remote_addr": get_remote_address()},
                    )
                    return redirect(url_for("index", message="This login link is no longer valid!"))

    except psycopg2.Error as e:
        logger.error(
            "Database error during authentication",
            extra={
                "email": email,
                "error": str(e),
                "error_type": type(e).__name__,
                "remote_addr": get_remote_address(),
            },
            exc_info=True,
        )
        return redirect(url_for("index", message="An error occurred. Please try again."))

    resp = make_response(redirect(url_for("dashboard")))
    set_session_cookie(resp, email)
    return resp


@app.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard – shows link-telegram or filters depending on state."""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Advisory lock on the email to prevent duplicate row creation
                # when two requests race for a new user.
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (request.email,))

                cur.execute(
                    "SELECT * FROM hestia.subscribers WHERE email_address = %s",
                    (request.email,),
                )
                subscriber = cur.fetchone()

                # Auto-create subscriber if none exists
                is_new_user = False
                if subscriber is None:
                    is_new_user = True
                    cur.execute(
                        "INSERT INTO hestia.subscribers (email_address) VALUES (%s)",
                        (request.email,),
                    )
                    cur.execute(
                        "SELECT * FROM hestia.subscribers WHERE email_address = %s",
                        (request.email,),
                    )
                    subscriber = cur.fetchone()

                # Fetch available cities and agencies for filter options
                cur.execute("SELECT DISTINCT city FROM hestia.homes")
                raw_cities = [row["city"] for row in cur.fetchall() if row["city"]]
                city_map = {}
                for city in raw_cities:
                    key = city.lower()
                    if key not in city_map:
                        city_map[key] = city
                        continue
                    existing = city_map[key]
                    if existing.isupper() and not city.isupper():
                        city_map[key] = city
                available_cities = sorted(
                    [city_map[key].title() if city_map[key].isupper() else city_map[key] for key in city_map]
                )

                cur.execute(
                    """
                    SELECT DISTINCT ON (agency) agency, user_info
                    FROM hestia.targets
                    WHERE enabled = true
                    ORDER BY agency
                    """
                )
                available_agencies = sorted(
                    [
                        {
                            "id": row["agency"],
                            "name": row["user_info"].get("agency", row["agency"])
                                if isinstance(row["user_info"], dict)
                                else row["agency"],
                        }
                        for row in cur.fetchall()
                    ],
                    key=lambda a: a["name"],
                )
    except psycopg2.Error as e:
        logger.error(
            "Database error loading dashboard",
            extra={
                "email": request.email,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return redirect(url_for("index", message="An error occurred. Please try again."))

    telegram_linked = subscriber.get("telegram_id") is not None

    return render_template(
        "dashboard.html",
        title="Dashboard",
        email=subscriber["email_address"],
        subscriber=subscriber,
        available_cities=available_cities,
        available_agencies=available_agencies,
        telegram_linked=telegram_linked,
        is_new_user=is_new_user,
    )


@app.route("/link-telegram")
@login_required
def link_telegram_page():
    """Show the link-telegram page for users who haven't linked Telegram yet."""
    email = request.email

    try:
        # If already fully linked, go to dashboard
        with get_db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id FROM hestia.subscribers WHERE email_address = %s AND telegram_id IS NOT NULL",
                    (email,),
                )
                row = cur.fetchone()
        if row is not None:
            return redirect(url_for("dashboard"))

        # Auto-generate a link code on page load
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM hestia.link_codes WHERE email_address = %s", (email,)
                )
                code = insert_link_code_with_retry(cur, email)

    except psycopg2.Error as e:
        logger.error(
            "Database error on link-telegram page",
            extra={
                "email": email,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return redirect(url_for("index", message="An error occurred. Please try again."))

    return render_template(
        "link_telegram.html",
        title="Link Telegram",
        email=email,
        link_code=code,
    )



@app.route("/api/link-code", methods=["POST"])
@login_required
def api_link_code():
    """Generate a Telegram link code and return it as JSON."""
    csrf_token = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
    if not validate_csrf_token(csrf_token):
        return jsonify({"error": "Invalid CSRF token"}), 403

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM hestia.link_codes WHERE email_address = %s",
                    (request.email,),
                )
                code = insert_link_code_with_retry(cur, request.email)
        return jsonify({"code": code, "expires_in": 300})
    except psycopg2.Error as e:
        logger.error(
            "Database error generating link code",
            extra={
                "email": request.email,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return jsonify({"error": "Database error"}), 500


@app.route("/link-telegram/check")
@limiter.limit("150 per hour; 500 per day")
def link_telegram_check():
    """Check if the user has linked Telegram. Merges rows if needed."""
    email = get_current_email()
    if email is None:
        return jsonify({"linked": False})
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM hestia.subscribers WHERE email_address = %s ORDER BY id",
                    (email,),
                )
                rows = cur.fetchall()

                # Find email-only and telegram rows
                email_only_row = None
                telegram_row = None
                for r in rows:
                    if r.get("telegram_id") is not None:
                        telegram_row = r
                    else:
                        email_only_row = r

                if telegram_row is not None and email_only_row is not None:
                    # Merge: copy telegram data to the email-only row, delete telegram row
                    cur.execute(
                        """UPDATE hestia.subscribers
                           SET telegram_id = %s,
                               telegram_enabled = %s,
                               filter_min_price = %s,
                               filter_max_price = %s,
                               filter_cities = %s,
                               filter_agencies = %s
                           WHERE id = %s""",
                        (
                            telegram_row["telegram_id"],
                            telegram_row["telegram_enabled"],
                            telegram_row["filter_min_price"],
                            telegram_row["filter_max_price"],
                            psycopg2.extras.Json(telegram_row["filter_cities"]),
                            psycopg2.extras.Json(telegram_row["filter_agencies"]),
                            email_only_row["id"],
                        ),
                    )
                    cur.execute(
                        "DELETE FROM hestia.subscribers WHERE id = %s",
                        (telegram_row["id"],),
                    )
                    logger.info(
                        "Merged telegram row into email row",
                        extra={
                            "email": email,
                            "email_row_id": email_only_row["id"],
                            "telegram_row_id": telegram_row["id"],
                        },
                    )
                    return jsonify({"linked": True})

                linked = telegram_row is not None
        return jsonify({"linked": linked})
    except psycopg2.Error as e:
        logger.error(
            "Database error checking telegram link status",
            extra={
                "email": email,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return jsonify({"error": "Database error", "linked": False}), 500


@app.route("/dashboard/filters", methods=["POST"])
@login_required
def update_filters():
    """Update subscriber filter preferences."""
    wants_json = request.headers.get("Accept", "").startswith("application/json") or "fetch" in request.headers.get("Sec-Fetch-Mode", "")

    # Validate CSRF token
    csrf_token = request.form.get("csrf_token", "")
    if not validate_csrf_token(csrf_token):
        if wants_json:
            return jsonify({"ok": False, "error": "Invalid CSRF token"}), 403
        return redirect(url_for("dashboard"))

    notifications_enabled = "notifications_enabled" in request.form
    min_price = request.form.get("min_price", "").strip() or None
    max_price = request.form.get("max_price", "").strip() or None

    filter_cities = psycopg2.extras.Json([c.lower() for c in request.form.getlist("filter_cities")])
    submitted_agencies = request.form.getlist("filter_agencies")

    try:
        min_price = int(min_price) if min_price is not None else None
    except (ValueError, TypeError):
        min_price = None
    try:
        max_price = int(max_price) if max_price is not None else None
    except (ValueError, TypeError):
        max_price = None

    if min_price is not None:
        min_price = max(0, min(min_price, 99999))
    if max_price is not None:
        max_price = max(0, min(max_price, 99999))

    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Fetch the user's current filter_agencies so we can preserve
                # agencies that are disabled in hestia.targets (hidden from UI).
                cur.execute(
                    "SELECT filter_agencies FROM hestia.subscribers WHERE email_address = %s",
                    (request.email,),
                )
                row = cur.fetchone()
                existing_agencies = row["filter_agencies"] or [] if row else []

                # Get currently enabled agency IDs (the ones shown in the form)
                cur.execute(
                    "SELECT agency FROM hestia.targets WHERE enabled = true"
                )
                enabled_agency_ids = {r["agency"] for r in cur.fetchall()}

                # Hidden agencies = previously selected but not shown in the form
                hidden_agencies = [
                    a for a in existing_agencies if a not in enabled_agency_ids
                ]

                filter_agencies = psycopg2.extras.Json(
                    submitted_agencies + hidden_agencies
                )

                cur.execute(
                    """
                    UPDATE hestia.subscribers
                    SET telegram_enabled = %s,
                        filter_min_price = %s,
                        filter_max_price = %s,
                        filter_cities = %s,
                        filter_agencies = %s
                    WHERE email_address = %s
                    """,
                    (notifications_enabled, min_price, max_price, filter_cities, filter_agencies, request.email),
                )

    except psycopg2.Error as e:
        logger.error(
            "Database error updating filters",
            extra={
                "email": request.email,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        if wants_json:
            return jsonify({"ok": False, "error": "Database error"}), 500
        return redirect(url_for("dashboard"))

    if wants_json:
        return jsonify({"ok": True})
    return redirect(url_for("dashboard"))


@app.route("/api/homes")
@limiter.limit("150 per hour")
@login_required
def api_homes():
    """Return homes matching the logged-in user's filters, with pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    offset = (page - 1) * per_page

    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT filter_min_price, filter_max_price, filter_cities, filter_agencies FROM hestia.subscribers WHERE email_address = %s",
                    (request.email,),
                )
                sub = cur.fetchone()
                if sub is None:
                    return jsonify({"homes": [], "total": 0, "page": page, "per_page": per_page})

                min_price = sub["filter_min_price"]
                max_price = sub["filter_max_price"]
                cities = sub["filter_cities"] or []
                agencies = sub["filter_agencies"] or []

                if not cities and not agencies:
                    return jsonify({"homes": [], "total": 0, "page": page, "per_page": per_page})

                conditions = ["h.price >= %s", "h.price <= %s", "h.date_added >= %s"]
                params = [min_price, max_price, datetime.now(timezone.utc) - timedelta(weeks=4)]

                if cities:
                    conditions.append("LOWER(h.city) = ANY(%s)")
                    params.append([c.lower() for c in cities])

                if agencies:
                    conditions.append("h.agency = ANY(%s)")
                    params.append(agencies)

                where = " AND ".join(conditions)

                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM hestia.homes h WHERE {where}",
                    params,
                )
                total = cur.fetchone()["cnt"]

                cur.execute(
                    f"""
                    SELECT
                        h.url,
                        h.address,
                        h.city,
                        h.price,
                        COALESCE(t.user_info->>'agency', h.agency) AS agency,
                        h.date_added
                    FROM hestia.homes h
                    LEFT JOIN hestia.targets t ON t.agency = h.agency
                    WHERE {where}
                    ORDER BY h.date_added DESC
                    LIMIT %s OFFSET %s
                    """,
                    params + [per_page, offset],
                )
                homes = cur.fetchall()

        # Serialize date_added to ISO string in UTC
        for h in homes:
            if h.get("date_added") and hasattr(h["date_added"], "isoformat"):
                dt = h["date_added"]
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                h["date_added"] = dt.isoformat()

        return jsonify({
            "homes": homes,
            "total": total,
            "page": page,
            "per_page": per_page,
        })
    except psycopg2.Error as e:
        logger.error(
            "Database error fetching homes",
            extra={
                "email": request.email,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return jsonify({"error": "Database error"}), 500


class PreviewImageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.candidates = []
        self.seen_img = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "meta":
            key = (attrs_dict.get("property") or attrs_dict.get("name") or "").lower()
            content = attrs_dict.get("content")
            if not content:
                return
            if key == "og:image":
                self._add_candidate(content, 1)
            elif key == "twitter:image":
                self._add_candidate(content, 2)
        elif tag == "link":
            rel = (attrs_dict.get("rel") or "").lower()
            href = attrs_dict.get("href")
            if href and rel == "image_src":
                self._add_candidate(href, 3)
        elif tag == "img" and not self.seen_img:
            src = attrs_dict.get("src")
            if src:
                self.seen_img = True
                self._add_candidate(src, 4)

    def _add_candidate(self, value, priority):
        value_lower = value.lower().split("?", 1)[0]
        if value_lower.endswith(".svg"):
            return
        self.candidates.append((priority, value))

    def ordered_candidates(self):
        return [urljoin(self.base_url, value) for _, value in sorted(self.candidates, key=lambda c: c[0])]


def _looks_like_image_url(url):
    path = urlparse(url).path.lower()
    for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif"):
        if path.endswith(ext):
            return True
    return False


def _safe_urlopen(url, headers, method="GET", timeout=5, max_redirects=3):
    """Open a URL with redirect validation and public-host enforcement."""
    current = url
    for _ in range(max_redirects + 1):
        parsed = urlparse(current)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("unsupported scheme")
        if not _is_public_host(parsed.hostname):
            raise ValueError("non-public host")
        req = Request(current, method=method, headers=headers)
        try:
            return urlopen(req, timeout=timeout)
        except Exception as e:
            if hasattr(e, "code") and e.code in {301, 302, 303, 307, 308}:
                location = e.headers.get("Location")
                if not location:
                    raise
                current = urljoin(current, location)
                continue
            raise
    raise ValueError("too many redirects")


def _cleanup_recent_logins(now):
    """Evict stale entries and cap size to avoid unbounded growth."""
    cutoff = now - (RECENT_LOGIN_WINDOW_SECONDS * 2)
    stale = [email for email, ts in RECENT_LOGIN_REQUESTS.items() if ts < cutoff]
    for email in stale:
        RECENT_LOGIN_REQUESTS.pop(email, None)
    if len(RECENT_LOGIN_REQUESTS) > RECENT_LOGIN_MAX_ENTRIES:
        # Evict oldest entries
        oldest = sorted(RECENT_LOGIN_REQUESTS.items(), key=lambda kv: kv[1])[:len(RECENT_LOGIN_REQUESTS) - RECENT_LOGIN_MAX_ENTRIES]
        for email, _ in oldest:
            RECENT_LOGIN_REQUESTS.pop(email, None)


def _is_image_url(url):
    if _looks_like_image_url(url):
        return True
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not _is_public_host(parsed.hostname):
        return False
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        with _safe_urlopen(url, headers, method="HEAD", timeout=5) as resp:
            content_type = resp.headers.get("Content-Type", "")
            return content_type.startswith("image/")
    except Exception:
        return False


def _is_public_host(hostname):
    if not hostname:
        return False
    if hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_global
    except ValueError:
        try:
            resolved = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(resolved)
            return ip.is_global
        except Exception:
            return False


def _preview_cache_get(url):
    now = datetime.now(timezone.utc)
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT url, status, image_url, image_bytes, content_type, expires_at
                    FROM hestia.preview_cache
                    WHERE url = %s
                    """,
                    (url,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                if row["expires_at"] and row["expires_at"] <= now:
                    cur.execute("DELETE FROM hestia.preview_cache WHERE url = %s", (url,))
                    return None
                return row
    except psycopg2.Error:
        logger.exception("Preview cache lookup failed", extra={"url": url})
        return None


def _preview_cache_set(url, status, ttl, image_url=None, image_bytes=None, content_type=None):
    now = datetime.now(timezone.utc)
    expires_at = now + ttl
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO hestia.preview_cache
                        (url, status, image_url, image_bytes, content_type, fetched_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE
                    SET status = EXCLUDED.status,
                        image_url = EXCLUDED.image_url,
                        image_bytes = EXCLUDED.image_bytes,
                        content_type = EXCLUDED.content_type,
                        fetched_at = EXCLUDED.fetched_at,
                        expires_at = EXCLUDED.expires_at
                    """,
                    (url, status, image_url, image_bytes, content_type, now, expires_at),
                )
    except psycopg2.Error:
        logger.exception("Preview cache write failed", extra={"url": url, "status": status})


@app.route("/api/preview-image")
@login_required
@limiter.limit("50 per minute; 250 per hour")
def api_preview_image():
    url = request.args.get("url", "")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return jsonify({"image_url": ""})
    if not _is_public_host(parsed.hostname):
        return jsonify({"image_url": ""}), 400
    cached = _preview_cache_get(url)
    if cached:
        if cached["status"] == "ok" and cached.get("image_url"):
            return jsonify({"image_url": cached["image_url"]})
        return jsonify({"image_url": ""})

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
        }
        with _safe_urlopen(url, headers, method="GET", timeout=5) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if content_type.startswith("image/"):
                _preview_cache_set(url, "ok", PREVIEW_CACHE_OK_TTL, image_url=url)
                return jsonify({"image_url": url})
            if "text/html" not in content_type:
                _preview_cache_set(url, "empty", PREVIEW_CACHE_EMPTY_TTL)
                return jsonify({"image_url": ""})
            html = resp.read(1024 * 1024).decode("utf-8", "ignore")
    except Exception:
        _preview_cache_set(url, "error", PREVIEW_CACHE_ERROR_TTL)
        return jsonify({"image_url": ""})

    parser = PreviewImageParser(url)
    try:
        parser.feed(html)
    except Exception:
        _preview_cache_set(url, "error", PREVIEW_CACHE_ERROR_TTL)
        return jsonify({"image_url": ""})

    for candidate in parser.ordered_candidates():
        if _is_image_url(candidate):
            _preview_cache_set(url, "ok", PREVIEW_CACHE_OK_TTL, image_url=candidate)
            return jsonify({"image_url": candidate})
    _preview_cache_set(url, "empty", PREVIEW_CACHE_EMPTY_TTL)
    return jsonify({"image_url": ""})


@app.route("/api/preview-image-raw")
@login_required
@limiter.limit("50 per minute; 250 per hour")
def api_preview_image_raw():
    url = request.args.get("url", "")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return ("", 400)
    if not _is_public_host(parsed.hostname):
        return ("", 400)
    cached = _preview_cache_get(url)
    if cached:
        if cached["status"] == "ok" and cached.get("image_bytes") and cached.get("content_type"):
            # Convert memoryview to bytes if needed (PostgreSQL bytea returns memoryview)
            image_data = bytes(cached["image_bytes"]) if isinstance(cached["image_bytes"], memoryview) else cached["image_bytes"]
            response = make_response(image_data)
            response.headers["Content-Type"] = cached["content_type"]
            response.headers["Cache-Control"] = "public, max-age=3600"
            return response
        if cached["status"] in {"empty", "error"}:
            return ("", 404)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "Referer": f"{parsed.scheme}://{parsed.netloc}/",
        }
        with _safe_urlopen(url, headers, method="GET", timeout=5) as resp:
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            data = resp.read(PREVIEW_IMAGE_MAX_BYTES)
    except Exception:
        _preview_cache_set(url, "error", PREVIEW_CACHE_ERROR_TTL)
        return ("", 502)

    if not content_type.startswith("image/"):
        _preview_cache_set(url, "error", PREVIEW_CACHE_ERROR_TTL)
        return ("", 502)

    _preview_cache_set(url, "ok", PREVIEW_CACHE_OK_TTL, image_url=url, image_bytes=data, content_type=content_type)

    response = make_response(data)
    response.headers["Content-Type"] = content_type
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/avatar")
def avatar():
    """Serve the Hestia avatar image."""
    return send_from_directory(app.static_folder, "hestia.jpeg")


@app.route("/api/statistics")
@limiter.limit("30 per minute")
@login_required
def api_statistics():
    """Return public statistics about homes and subscribers."""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT COUNT(*) AS cnt FROM hestia.homes")
                total_homes = cur.fetchone()["cnt"]

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM hestia.homes WHERE date_added >= NOW() - INTERVAL '24 hours'"
                )
                homes_today = cur.fetchone()["cnt"]

                cur.execute(
                    "SELECT city, COUNT(*) AS count FROM hestia.homes GROUP BY city ORDER BY count DESC LIMIT 5"
                )
                top_cities = [{"city": r["city"], "count": r["count"]} for r in cur.fetchall()]

                cur.execute(
                    "SELECT agency, COUNT(*) AS count FROM hestia.homes WHERE agency IS NOT NULL GROUP BY agency ORDER BY count DESC LIMIT 5"
                )
                top_agencies = [{"agency": r["agency"], "count": r["count"]} for r in cur.fetchall()]

                cur.execute("SELECT COUNT(*) AS cnt FROM hestia.subscribers")
                total_subscribers = cur.fetchone()["cnt"]

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM hestia.subscribers WHERE date_added >= date_trunc('month', CURRENT_DATE)"
                )
                subscribers_this_month = cur.fetchone()["cnt"]

        return jsonify({
            "total_homes": total_homes,
            "homes_today": homes_today,
            "top_cities": top_cities,
            "top_agencies": top_agencies,
            "total_subscribers": total_subscribers,
            "subscribers_this_month": subscribers_this_month,
        })
    except psycopg2.Error as e:
        logger.error(
            "Database error fetching statistics",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        return jsonify({"error": "Database error"}), 500


@app.route("/api/donation-link")
def donation_link():
    """Return the donation link from the database."""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT donation_link FROM hestia.meta WHERE id = 'default'")
                row = cur.fetchone()
        url = row["donation_link"] if row else None
        if url:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                url = None
        return jsonify({"url": url})
    except psycopg2.Error as e:
        logger.error(
            "Database error fetching donation link",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        return jsonify({"error": "Database error"}), 500


@app.route("/health")
def health():
    """Health check endpoint for container orchestration."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return jsonify({"status": "healthy"}), 200
    except Exception:
        return jsonify({"status": "unhealthy"}), 503


@app.route("/logout")
def logout():
    """Clear session cookie and redirect to landing page."""
    resp = make_response(redirect(url_for("index")))
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp


@app.route("/test-image-loading")
@login_required
def test_image_loading():
    """Diagnostic page for troubleshooting image loading issues."""
    with open("test_image_loading.html") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def close_db_pool():
    """Close all connections in the database pool."""
    if db_pool:
        logger.info("Closing database connection pool")
        db_pool.closeall()

atexit.register(close_db_pool)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info(
        "Starting Hestia web",
        extra={
            "host": "0.0.0.0",
            "port": 5050,
            "log_format": os.getenv("LOG_FORMAT", "plain"),
        },
    )
    app.run(host="0.0.0.0", port=5050)

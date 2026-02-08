import psycopg2
import logging
from telegram import Chat
from typing import Literal
from datetime import datetime
from psycopg2.extras import RealDictCursor, RealDictRow

from hestia_utils.secrets import DB

logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s",
    level=logging.WARNING,
    filename="/data/hestia.log"
)

LANG_CACHE = {}


def get_connection():
    return psycopg2.connect(database=DB["database"],
                            host=DB["host"],
                            user=DB["user"],
                            password=DB["password"],
                            port=DB["port"])


### Read actions

def fetch_one(query: str, params: list[str] = []) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            result = cur.fetchone()
    except Exception as e:
        logging.error(f"Database read error: {repr(e)}\nQuery: {query}\nParams: {params}")
        result = {}
    finally:
        if conn: conn.close()
    if not result:
        return {}
    return result

def fetch_all(query: str, params: list[str] = []) -> list[RealDictRow]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            result = cur.fetchall()
    except Exception as e:
        logging.error(f"Database read error: {repr(e)}\nQuery: {query}\nParams: {params}")
        result = []
    finally:
        if conn: conn.close()
    return result

def get_dev_mode() -> bool:
    result = fetch_one("SELECT devmode_enabled FROM hestia.meta WHERE id = 'default'")
    if result and "devmode_enabled" in result:
        return result["devmode_enabled"]
    return True
def get_scraper_halted() -> bool:
    result = fetch_one("SELECT scraper_halted FROM hestia.meta WHERE id = 'default'")
    if result and "scraper_halted" in result:
        return result["scraper_halted"]
    return True
def get_donation_link() -> str:
    result = fetch_one("SELECT donation_link FROM hestia.meta WHERE id = 'default'")
    if result and "donation_link" in result:
        return result["donation_link"]
    return ""
def get_donation_link_updated() -> datetime:
    result = fetch_one("SELECT donation_link_updated FROM hestia.meta WHERE id = 'default'")
    if result and "donation_link_updated" in result:
        return result["donation_link_updated"]
    return datetime.min

def get_user_lang(telegram_id: int) -> Literal["en", "nl"]:
    if telegram_id in LANG_CACHE:
        return LANG_CACHE[telegram_id]
    result = fetch_one("SELECT lang FROM hestia.subscribers WHERE telegram_id = %s", [str(telegram_id)])
    if result and "lang" in result and result["lang"] in ["en", "nl"]:
        LANG_CACHE[telegram_id] = result["lang"]
        return result["lang"]
    return "en"


### Write actions

def _write(query: str, params: list[str] = []) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
    except Exception as e:
        logging.error(f"Database write error: {repr(e)}\nQuery: {query}\nParams: {params}")
    finally:
        if conn: conn.close()

def add_home(url: str, address: str, city: str, price: int, agency: str, date_added: str) -> None:
    _write("INSERT INTO hestia.homes (url, address, city, price, agency, date_added) VALUES (%s, %s, %s, %s, %s, %s)", [url, address, city, str(price), agency, date_added])
def add_user(telegram_id: int) -> None:
    _write("INSERT INTO hestia.subscribers VALUES (DEFAULT, '2099-01-01T00:00:00', DEFAULT, DEFAULT, DEFAULT, DEFAULT, true, %s, DEFAULT)", [str(telegram_id)])
def enable_user(telegram_id: int) -> None:
    _write("UPDATE hestia.subscribers SET telegram_enabled = true WHERE telegram_id = %s", [str(telegram_id)])
def disable_user(telegram_id: int) -> None:
    _write("UPDATE hestia.subscribers SET telegram_enabled = false WHERE telegram_id = %s", [str(telegram_id)])
def halt_scraper() -> None:
    _write("UPDATE hestia.meta SET scraper_halted = true WHERE id = 'default'")
def resume_scraper() -> None:
    _write("UPDATE hestia.meta SET scraper_halted = false WHERE id = 'default'")
def enable_dev_mode() -> None:
    _write("UPDATE hestia.meta SET devmode_enabled = true WHERE id = 'default'")
def disable_dev_mode() -> None:
    _write("UPDATE hestia.meta SET devmode_enabled = false WHERE id = 'default'")
def update_donation_link(link: str) -> None:
    _write("UPDATE hestia.meta SET donation_link = %s, donation_link_updated = now() WHERE id = 'default'", [link])

def set_filter_minprice(telegram_chat: Chat, min_price: int) -> None:
    _write("UPDATE hestia.subscribers SET filter_min_price = %s WHERE telegram_id = %s", [str(min_price), str(telegram_chat.id)])
def set_filter_maxprice(telegram_chat: Chat, max_price: int) -> None:
    _write("UPDATE hestia.subscribers SET filter_max_price = %s WHERE telegram_id = %s", [str(max_price), str(telegram_chat.id)])
def set_filter_cities(telegram_chat: Chat, cities: str) -> None:
    _write("UPDATE hestia.subscribers SET filter_cities = %s WHERE telegram_id = %s", [str(cities).replace("'", '"'), str(telegram_chat.id)])
def set_filter_agencies(telegram_chat: Chat, agencies: set[str]) -> None:
    _write("UPDATE hestia.subscribers SET filter_agencies = %s WHERE telegram_id = %s", [str(list(agencies)).replace("'", '"'), str(telegram_chat.id)])

def set_user_lang(telegram_chat: Chat, lang: Literal["en", "nl"]) -> None:
    _write("UPDATE hestia.subscribers SET lang = %s WHERE telegram_id = %s", [lang, str(telegram_chat.id)])
    LANG_CACHE[telegram_chat.id] = lang


FILTER_COLUMNS = ["filter_min_price", "filter_max_price", "filter_cities", "filter_agencies"]


def _load_filter_defaults(cur) -> dict:
    cur.execute(
        """
        SELECT column_name, column_default
        FROM information_schema.columns
        WHERE table_schema = 'hestia'
          AND table_name = 'subscribers'
          AND column_name = ANY(%s)
        """,
        [FILTER_COLUMNS],
    )
    defaults = {row["column_name"]: row["column_default"] for row in cur.fetchall()}
    for col in FILTER_COLUMNS:
        if col not in defaults or defaults[col] is None:
            defaults[col] = "NULL"
    return defaults


def _filters_are_default(cur, where_sql: str, params: list[str], defaults: dict) -> bool:
    checks = [f"{col} IS NOT DISTINCT FROM {defaults[col]} AS {col}_default" for col in FILTER_COLUMNS]
    query = f"SELECT {', '.join(checks)} FROM hestia.subscribers WHERE {where_sql}"
    cur.execute(query, params)
    result = cur.fetchone()
    if not result:
        return False
    return all(result.values())


def link_account(telegram_id: int, code: str) -> Literal["success", "invalid_code", "already_linked"]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Look up the code
            cur.execute("SELECT email_address FROM hestia.link_codes WHERE code = %s AND expires_at > now()", [code])
            row = cur.fetchone()
            if not row:
                return "invalid_code"

            email = row["email_address"]

            # Check if the Telegram user already has an email linked
            cur.execute("SELECT email_address FROM hestia.subscribers WHERE telegram_id = %s", [str(telegram_id)])
            sub = cur.fetchone()
            if sub and sub["email_address"]:
                return "already_linked"

            # Read both subscriber rows and compare filters with DB defaults
            cur.execute("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", [str(telegram_id)])
            tg_sub = cur.fetchone()
            cur.execute("SELECT * FROM hestia.subscribers WHERE email_address = %s AND telegram_id IS NULL", [email])
            web_sub = cur.fetchone()

            defaults = _load_filter_defaults(cur)
            tg_default = _filters_are_default(cur, "telegram_id = %s", [str(telegram_id)], defaults)
            web_default = True
            if web_sub:
                web_default = _filters_are_default(cur, "email_address = %s AND telegram_id IS NULL", [email], defaults)

            # Overwrite the default filters with the non-default filters
            if tg_sub and web_sub and tg_default and not web_default:
                cur.execute(
                    """
                    UPDATE hestia.subscribers
                    SET filter_min_price = %s,
                        filter_max_price = %s,
                        filter_cities = %s,
                        filter_agencies = %s
                    WHERE telegram_id = %s
                    """,
                    [
                        web_sub["filter_min_price"],
                        web_sub["filter_max_price"],
                        web_sub["filter_cities"],
                        web_sub["filter_agencies"],
                        str(telegram_id),
                    ],
                )

            # Set email on the Telegram user's row
            cur.execute("UPDATE hestia.subscribers SET email_address = %s WHERE telegram_id = %s", [email, str(telegram_id)])

            # Delete the web-only subscriber row (has email but no telegram_id)
            cur.execute("DELETE FROM hestia.subscribers WHERE email_address = %s AND telegram_id IS NULL", [email])

            # Delete the used link code
            cur.execute("DELETE FROM hestia.link_codes WHERE code = %s", [code])

            conn.commit()
            return "success"
    except Exception as e:
        conn.rollback()
        logging.error(f"Database error in link_account: {repr(e)}")
        return "invalid_code"
    finally:
        if conn: conn.close()

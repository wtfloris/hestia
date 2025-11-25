import psycopg2
import logging
from datetime import datetime
from psycopg2.extras import RealDictCursor, RealDictRow
from telegram import Chat

from hestia_utils.secrets import DB

logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s",
    level=logging.WARNING,
    filename="/data/hestia.log"
)


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
    _write("INSERT INTO hestia.subscribers VALUES (DEFAULT, '2099-01-01T00:00:00', DEFAULT, DEFAULT, DEFAULT, DEFAULT, true, %s)", [str(telegram_id)])
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
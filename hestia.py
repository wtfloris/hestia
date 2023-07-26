import psycopg2
import telegram
import logging
from psycopg2.extras import RealDictCursor
from secrets import OWN_CHAT_ID, TOKEN, DB

# TODO this could be a class

def query_db(query, fetchOne=False):
# TODO error handling
    db = psycopg2.connect(database=DB["database"],
                            host=DB["host"],
                            user=DB["user"],
                            password=DB["password"],
                            port=DB["port"])
    
    cursor = db.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query)
    
    # Try, because not all queries will return data
    try:
        if fetchOne:
            result = cursor.fetchone()
        else:
            result = cursor.fetchall()
    except:
        result = None
    
    db.commit()
    cursor.close()
    db.close()
    
    return result

WORKDIR = query_db("SELECT workdir FROM hestia.meta")[0]["workdir"]

logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s",
    level=logging.WARNING,
    filename=WORKDIR + "hestia.log"
)

BOT = telegram.Bot(TOKEN)

HOUSE_EMOJI = "\U0001F3E0"
LINK_EMOJI = "\U0001F517"

# The identifier of the used settings in the database (default = default)
SETTINGS_ID = "default"

def check_dev_mode():
    return query_db("SELECT devmode_enabled FROM hestia.meta", fetchOne=True)["devmode_enabled"]
    
def check_scraper_halted():
    return query_db("SELECT scraper_halted FROM hestia.meta", fetchOne=True)["scraper_halted"]

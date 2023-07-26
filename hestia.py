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
    
    if fetchOne:
        result = cursor.fetchone()
    else:
        result = cursor.fetchall()
        
    cursor.close()
    db.close()
    
    return result

WORKDIR = query_db("SELECT workdir FROM hestia.meta")[0]["workdir"]

BOT = telegram.Bot(TOKEN)

HOUSE_EMOJI = "\U0001F3E0"
LINK_EMOJI = "\U0001F517"

# The identifier of the used settings in the database (default = default)
SETTINGS_ID = "default"

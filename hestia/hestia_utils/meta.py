import logging
import telegram

import hestia_utils.db as db
from hestia_utils.secrets import TOKEN

def escape_markdownv2(text: str) -> str:
    text = text.replace('.', r'\.')
    text = text.replace('!', r'\!')
    text = text.replace('+', r'\+')
    text = text.replace('-', r'\-')
    text = text.replace('*', r'\*')
    text = text.replace('|', r'\|')
    return text

WORKDIR = "./"
get_workdir = db.fetch_one("SELECT workdir FROM hestia.meta")
if get_workdir and "workdir" in get_workdir:
    WORKDIR = get_workdir["workdir"]

logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s",
    level=logging.WARNING,
    filename=WORKDIR + "hestia.log"
)

BOT = telegram.Bot(TOKEN)

HOUSE_EMOJI = "\U0001F3E0"
LINK_EMOJI = "\U0001F517"
EURO_EMOJI = "\U0001F4B6"
LOVE_EMOJI = "\U0001F970"
CHECK_EMOJI = "\U00002705"
CROSS_EMOJI = "\U0000274C"

# The Dockerfile replaces this with the git commit id
APP_VERSION = ''

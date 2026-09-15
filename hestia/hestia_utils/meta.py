import logging
import telegram
from telegram.helpers import escape_markdown

from hestia_utils.secrets import TOKEN


def escape_markdownv2(text: str) -> str:
    """Escape text for MarkdownV2 body content."""
    return escape_markdown(text, version=2)


def escape_markdownv2_url(url: str) -> str:
    """Escape a URL for the (...) part of a MarkdownV2 inline link.

    Only ')' and '\\' are reserved there — escaping the full special set
    would corrupt the URL.
    """
    return escape_markdown(url, version=2, entity_type="text_link")


logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    level=logging.WARNING,
    filename="/data/hestia.log"
)

BOT = telegram.Bot(TOKEN)

# Base URL of the web service, used to build affiliate /go/<id> redirect links
HESTIA_BASE_URL = "https://hestia.bot"

HOUSE_EMOJI = "\U0001F3E0"
LINK_EMOJI = "\U0001F517"
EURO_EMOJI = "\U0001F4B6"
LOVE_EMOJI = "\U0001F970"
CHECK_EMOJI = "\U00002705"
CROSS_EMOJI = "\U0000274C"
SQM_EMOJI = "\U0001F4D0"

# The Dockerfile replaces this with the git commit id
APP_VERSION = ''

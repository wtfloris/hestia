# Hestia

Real estate rental listing scraper that broadcasts results via Telegram.

## Architecture

- **Scraper** (`hestia/scraper.py`): Runs every 5 min via cron in Docker. Scrapes rental sites, stores new listings in PostgreSQL, notifies subscribers via Telegram.
- **Bot** (`hestia/bot.py`): Telegram bot for user subscriptions and admin commands.
- **Parsers** (`hestia/hestia_utils/parser.py`): Per-agency parsers that take a `requests.Response` and produce `Home` objects. JSON API responses preferred; fall back to BeautifulSoup HTML parsing.
- **DB** (`hestia/hestia_utils/db.py`): PostgreSQL via psycopg2. Schema in `misc/hestia.ddl`.

## Tech Stack

- Python 3.11, Docker (two containers: bot + scraper)
- PostgreSQL 15, python-telegram-bot, requests, BeautifulSoup4, chompjs
- Secrets in `hestia/hestia_utils/secrets.py` (not committed; see `misc/secrets.py.template`)

## Build & Run

```sh
bash build.sh        # build + run production containers
bash build.sh dev    # build + run dev containers
bash build.sh -y     # skip confirmation prompt
```

## Git

- NEVER `git add` `misc/maintenance.py` — it contains a secret token.

## Key Conventions

- Branches: `master` (main), `dev` (development)
- New website support = new parser function in `parser.py` + a DB target row
- `Home` object fields: `agency`, `address`, `city`, `url`, `price` (int)
- Prices must be parsed to plain integers (strip currency symbols, dots, commas)
- Filter out already-rented listings in the parser when possible

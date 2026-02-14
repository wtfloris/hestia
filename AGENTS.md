# Hestia

Real estate rental listing scraper that broadcasts results via Telegram.

## Architecture

- **Scraper** (`hestia/scraper.py`): Runs every 5 min via cron in Docker. Scrapes rental sites, stores new listings in PostgreSQL, notifies subscribers via Telegram.
- **Bot** (`hestia/bot.py`): Telegram bot for user subscriptions and admin commands.
- **Parsers** (`hestia/hestia_utils/parser.py`): Per-agency parsers that take a `requests.Response` and produce `Home` objects. JSON API responses preferred; fall back to BeautifulSoup HTML parsing.
- **DB** (`hestia/hestia_utils/db.py`): PostgreSQL via psycopg2. Schema in `misc/hestia.ddl`.
- **Web** (`web/`): Web portal

## Tech Stack

- Python 3.11, Docker (two containers: bot + scraper)
- PostgreSQL 15, python-telegram-bot, requests, BeautifulSoup4, chompjs
- Secrets in `hestia/hestia_utils/secrets.py` (not committed; see `misc/secrets.py.template`)

## Python Environment

- Always use the local `.venv` for running Python: `source .venv/bin/activate` or `.venv/bin/python3`.

## Build & Run

```sh
bash build.sh -y        # build + run production containers
bash build.sh dev -y    # build + run dev containers (if you are in hestia-dev)
```

Manual scrape:
- Ensure that scraper_halted in the hestia.meta table is false
```
docker exec hestia-scraper-dev python3 hestia/scraper.py  # run the scraper manually (dev)
```

## Git

- NEVER `git add` `misc/maintenance.py` — it contains a secret token.
- Keep commit messages very short and concise, don't add "created by claude/codex" or anything

## Database

- The schema is available in `misc/hestia.ddl`
- Access the PostgreSQL database using `docker exec hestia-database-dev psql hestia claude`. NEVER use another user to access the database. This user has some safeguards in the permissions.
- To enable/disable targets, run the SQL directly against the database (e.g. `UPDATE hestia.targets SET enabled = false WHERE agency = 'x'`). Do not add helper functions for this.

## Key Conventions

- New website support = new parser function in `parser.py` + a DB target row
- `Home` object fields: `agency`, `address`, `city`, `url`, `price` (int)
- Prices must be parsed to plain integers (strip currency symbols, dots, commas)
- Filter out already-rented listings in the parser when possible
- Explicitly filter out unavailable statuses such as `verhuurd`, `onder optie`, `withdrawn`, and `rentedwithreservation`
- Filter out project/complex listings that don't have a house number in the address (the address is used as a unique identifier)
- When testing a new parser, always verify at least 2 parsed listing URLs return HTTP 200
- When testing a new parser, verify all parsed results contain a house number in the address

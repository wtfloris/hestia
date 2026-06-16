"""Session fixtures for end-to-end tests.

Spins up a throwaway Postgres 16 container, applies the production DDL,
and rewires hestia_utils.secrets.DB so every call that goes through
db.get_connection() lands in that container. Only PDOK and telegram
send_message need to be mocked in the tests themselves.

If Docker isn't available or the image can't run, the whole e2e suite
is skipped rather than failing.
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import psycopg2
import pytest

import hestia_utils.secrets as secrets

IMAGE = "postgres:16"
CONTAINER_NAME = "hestia-e2e-pg"
DB_NAME = "hestia_e2e"
DB_USER = "hestia"
DB_PASSWORD = "hestia_e2e_pw"
DDL_PATH = Path(__file__).resolve().parents[2] / "misc" / "hestia.ddl"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    r = subprocess.run(["docker", "info"], capture_output=True)
    return r.returncode == 0


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(host: str, port: int, timeout: float = 40.0) -> None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(
                host=host, port=port, user=DB_USER,
                password=DB_PASSWORD, database=DB_NAME,
                connect_timeout=2,
            )
            conn.close()
            return
        except psycopg2.OperationalError as e:
            last = e
            time.sleep(0.5)
    raise RuntimeError(f"Postgres never became ready: {last!r}")


@pytest.fixture(scope="session")
def _pg_container():
    if not _docker_available():
        pytest.skip("Docker daemon unavailable — skipping e2e suite")

    # Clean up a stale container from an aborted earlier run, if any.
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)

    port = _free_port()
    # --network host sidesteps the host's iptables userland-proxy path, which
    # can be broken on kernels missing xt_tcp / nf_conntrack modules. We pick
    # a free high port and tell Postgres itself to bind there (`-c port=...`).
    run = subprocess.run(
        [
            "docker", "run", "-d", "--rm",
            "--name", CONTAINER_NAME,
            "--network", "host",
            "-e", f"POSTGRES_DB={DB_NAME}",
            "-e", f"POSTGRES_USER={DB_USER}",
            "-e", f"POSTGRES_PASSWORD={DB_PASSWORD}",
            IMAGE,
            "-c", f"port={port}",
        ],
        capture_output=True, text=True,
    )
    if run.returncode != 0:
        pytest.skip(f"Could not start postgres container: {run.stderr.strip()}")

    try:
        _wait_ready("127.0.0.1", port)
        conn = psycopg2.connect(
            host="127.0.0.1", port=port, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME,
        )
        try:
            with conn.cursor() as cur:
                # The production DDL says `AUTHORIZATION postgres`; in our test
                # container the superuser is DB_USER, and the postgres role
                # doesn't exist. Create it so AUTHORIZATION resolves.
                cur.execute(
                    "DO $$ BEGIN "
                    "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='postgres') "
                    "THEN CREATE ROLE postgres; END IF; END $$;"
                )
                cur.execute(DDL_PATH.read_text())
                # Seed the meta row that db.get_dev_mode/get_scraper_halted expect.
                cur.execute(
                    "INSERT INTO hestia.meta "
                    "(id, devmode_enabled, scraper_halted, workdir) "
                    "VALUES ('default', false, false, '/tmp/')"
                )
            conn.commit()
        finally:
            conn.close()

        yield {
            "host": "127.0.0.1",
            "port": str(port),
            "database": DB_NAME,
            "user": DB_USER,
            "password": DB_PASSWORD,
        }
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)


@pytest.fixture(scope="session")
def pg(_pg_container):
    """Real DB connection info; also redirects hestia.secrets.DB for the session."""
    saved = dict(secrets.DB)
    secrets.DB.clear()
    secrets.DB.update(_pg_container)
    yield _pg_container
    secrets.DB.clear()
    secrets.DB.update(saved)


@pytest.fixture(autouse=True)
def _reset_state(pg):
    """Blank every table + in-process cache between tests."""
    import hestia_utils.db as db

    db.LANG_CACHE.clear()

    conn = psycopg2.connect(
        host=pg["host"], port=pg["port"], user=pg["user"],
        password=pg["password"], database=pg["database"],
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE hestia.homes, hestia.subscribers, hestia.geocode_cache, "
                "hestia.link_codes, hestia.magic_tokens, hestia.preview_cache, "
                "hestia.targets, hestia.error_rollups RESTART IDENTITY"
            )
        conn.commit()
    finally:
        conn.close()

    # Bust scraper.py's lru_cache for agency pretty-name lookups, if scraper imported.
    try:
        import scraper
        scraper._get_agency_pretty_name.cache_clear()
    except Exception:
        pass

    yield


@pytest.fixture
def mock_bot():
    """Swap meta.BOT with a MagicMock whose send_message is awaitable.

    Returns the mock so tests can inspect call_args_list. meta.BOT is restored
    at teardown.
    """
    import hestia_utils.meta as meta

    original = meta.BOT
    bot = MagicMock()
    bot.send_message = AsyncMock()
    meta.BOT = bot
    try:
        yield bot
    finally:
        meta.BOT = original

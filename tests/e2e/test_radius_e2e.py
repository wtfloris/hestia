"""End-to-end verification of the radius filter.

No mocks on the DB layer: every fetch/write hits the throwaway Postgres
container from conftest.py. We only stub:
  - PDOK HTTP (hestia_utils.geocode.requests.get)
  - Telegram send (meta.BOT.send_message, via the mock_bot fixture)

The tests cover the full pipeline:
  add_home  →  PDOK call  →  geocode_cache writeback  →  homes.lat/lon persisted
     ↓
  broadcast(homes)  →  reads cache if coords missing  →  haversine check
     ↓
  meta.BOT.send_message called only for subs whose radius matches
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import psycopg2
import pytest
from psycopg2.extras import RealDictCursor

import hestia_utils.db as db
from hestia_utils.parser import Home


AMSTERDAM = (52.3676, 4.9041)   # Dam square
ROTTERDAM = (51.9225, 4.4792)   # ~57 km from Amsterdam
UTRECHT = (52.0907, 5.1214)     # ~35 km from Amsterdam
DEN_HAAG = (52.0705, 4.3007)    # ~50 km from Amsterdam


# ---------- PDOK response helpers ---------------------------------------------

def _pdok_hit(lat: float, lon: float, score: float = 9.5):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {
        "response": {
            "docs": [{"score": score, "centroide_ll": f"POINT({lon} {lat})"}]
        }
    }
    return r


def _pdok_empty():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"response": {"docs": []}}
    return r


def _pdok_router(mapping: dict):
    """Build a requests.get side_effect that matches on the query string.

    mapping: substring → (lat, lon) tuple or None (means empty response).
    """
    def _side_effect(url, params=None, **kwargs):
        q = (params or {}).get("q", "") or ""
        for needle, target in mapping.items():
            if needle.lower() in q.lower():
                if target is None:
                    return _pdok_empty()
                return _pdok_hit(*target)
        return _pdok_empty()
    return _side_effect


# ---------- DB helpers --------------------------------------------------------

def _pg_conn(pg):
    return psycopg2.connect(
        host=pg["host"], port=pg["port"], user=pg["user"],
        password=pg["password"], database=pg["database"],
    )


def _insert_subscriber(
    pg,
    *,
    telegram_id,
    cities=("amsterdam", "rotterdam", "utrecht", "den haag"),
    filter_radius_km=None,
    filter_center=(None, None),
    min_price=0,
    max_price=10000,
):
    conn = _pg_conn(pg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO hestia.subscribers (
                    telegram_enabled, telegram_id,
                    filter_min_price, filter_max_price,
                    filter_cities, filter_agencies, filter_min_sqm,
                    filter_center_lat, filter_center_lon, filter_radius_km
                ) VALUES (true, %s, %s, %s, %s, %s, 0, %s, %s, %s)
                RETURNING id
                """,
                [
                    str(telegram_id),
                    min_price, max_price,
                    json.dumps(list(cities)),
                    json.dumps(["funda"]),
                    filter_center[0], filter_center[1], filter_radius_km,
                ],
            )
            sub_id = cur.fetchone()[0]
        conn.commit()
        return sub_id
    finally:
        conn.close()


def _seed_target(pg, agency="funda"):
    """scraper._get_agency_pretty_name reads hestia.targets; give it a row."""
    conn = _pg_conn(pg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO hestia.targets "
                "(agency, queryurl, method, user_info, post_data, headers, enabled) "
                "VALUES (%s, %s, 'GET', %s::jsonb, '{}'::jsonb, '{}'::json, true)",
                [agency, "http://example.test", json.dumps({"agency": "Funda"})],
            )
        conn.commit()
    finally:
        conn.close()


def _fetch_home(pg, url):
    conn = _pg_conn(pg)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM hestia.homes WHERE url = %s", [url])
            return cur.fetchone()
    finally:
        conn.close()


def _fetch_cache(pg, address, city):
    conn = _pg_conn(pg)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM hestia.geocode_cache WHERE address = %s AND city = %s",
                [address, city],
            )
            return cur.fetchone()
    finally:
        conn.close()


# ---------- Ingestion E2E -----------------------------------------------------

class TestAddHomeE2E:
    """db.add_home → geocode → homes row with coords + cache populated."""

    def test_add_home_persists_coords_and_cache(self, pg):
        with patch(
            "hestia_utils.geocode.requests.get",
            return_value=_pdok_hit(*AMSTERDAM),
        ):
            db.add_home(
                "http://example.com/a", "Kerkstraat 1", "Amsterdam",
                1500, "funda", datetime.now().isoformat(), 75,
            )

        home = _fetch_home(pg, "http://example.com/a")
        assert home is not None
        assert home["lat"] == pytest.approx(AMSTERDAM[0])
        assert home["lon"] == pytest.approx(AMSTERDAM[1])
        assert home["geocode_confidence"] == pytest.approx(9.5)

        cached = _fetch_cache(pg, "Kerkstraat 1", "Amsterdam")
        assert cached is not None
        assert cached["lat"] == pytest.approx(AMSTERDAM[0])
        assert cached["confidence"] == pytest.approx(9.5)

    def test_add_home_stores_null_on_pdok_miss(self, pg):
        """A geocoding miss must not drop the home — it inserts with NULL coords."""
        with patch(
            "hestia_utils.geocode.requests.get",
            return_value=_pdok_empty(),
        ):
            db.add_home(
                "http://example.com/b", "Onbekende Straat 1", "Nergensland",
                1500, "funda", datetime.now().isoformat(),
            )

        home = _fetch_home(pg, "http://example.com/b")
        assert home is not None
        assert home["lat"] is None
        assert home["lon"] is None

        # A null-cache entry must be stored so future lookups short-circuit.
        cached = _fetch_cache(pg, "Onbekende Straat 1", "Nergensland")
        assert cached is not None
        assert cached["lat"] is None

    def test_cache_prevents_second_pdok_call(self, pg):
        """Inserting the same address twice should hit PDOK once."""
        with patch(
            "hestia_utils.geocode.requests.get",
            return_value=_pdok_hit(*AMSTERDAM),
        ) as mock_get:
            db.add_home("http://example.com/c1", "Damstraat 5", "Amsterdam",
                        1200, "funda", datetime.now().isoformat())
            db.add_home("http://example.com/c2", "Damstraat 5", "Amsterdam",
                        1250, "funda", datetime.now().isoformat())
            assert mock_get.call_count == 1


# ---------- Broadcast E2E -----------------------------------------------------

class TestBroadcastRadiusE2E:
    """broadcast() must send listings only to subs whose radius matches."""

    def _run(self, coro):
        return asyncio.new_event_loop().run_until_complete(coro)

    def test_radius_filter_end_to_end(self, pg, mock_bot):
        """Near home reaches only the sub with the small radius.
        Far home reaches only the no-radius sub. City and agency filters
        are wide open so radius is the only differentiator."""
        _seed_target(pg)

        sub_near_only = 111
        sub_open = 222
        _insert_subscriber(
            pg, telegram_id=sub_near_only,
            filter_radius_km=5.0, filter_center=AMSTERDAM,
        )
        _insert_subscriber(pg, telegram_id=sub_open)

        pdok = _pdok_router({
            "Kerkstraat 1": AMSTERDAM,   # ~0 km from center
            "Coolsingel 1": ROTTERDAM,   # ~57 km
            "Domplein 1": UTRECHT,       # ~35 km
        })

        with patch("hestia_utils.geocode.requests.get", side_effect=pdok):
            db.add_home("http://x/near", "Kerkstraat 1", "Amsterdam",
                        1500, "funda", datetime.now().isoformat())
            db.add_home("http://x/far-rotterdam", "Coolsingel 1", "Rotterdam",
                        1500, "funda", datetime.now().isoformat())
            db.add_home("http://x/far-utrecht", "Domplein 1", "Utrecht",
                        1500, "funda", datetime.now().isoformat())

        homes = [
            Home(address="Kerkstraat 1", city="Amsterdam",
                 url="http://x/near", agency="funda", price=1500, sqm=-1),
            Home(address="Coolsingel 1", city="Rotterdam",
                 url="http://x/far-rotterdam", agency="funda", price=1500, sqm=-1),
            Home(address="Domplein 1", city="Utrecht",
                 url="http://x/far-utrecht", agency="funda", price=1500, sqm=-1),
        ]

        import scraper
        # No PDOK calls expected here — broadcast must hit the cache.
        with patch("hestia_utils.geocode.requests.get",
                   side_effect=AssertionError("broadcast should not call PDOK")):
            self._run(scraper.broadcast(homes))

        sent_by_chat: dict[str, list[str]] = {}
        for call in mock_bot.send_message.call_args_list:
            kwargs = call.kwargs
            sent_by_chat.setdefault(kwargs["chat_id"], []).append(kwargs["text"])

        near_only = sent_by_chat.get(str(sub_near_only), [])
        open_sub = sent_by_chat.get(str(sub_open), [])

        assert len(near_only) == 1, f"radius sub should get 1 home, got {near_only}"
        assert "Kerkstraat 1" in near_only[0]

        assert len(open_sub) == 3, (
            f"no-radius sub should get all 3 homes, got {open_sub}"
        )
        assert any("Kerkstraat 1" in m for m in open_sub)
        assert any("Coolsingel 1" in m for m in open_sub)
        assert any("Domplein 1" in m for m in open_sub)

    def test_home_without_coords_not_dropped_for_radius_sub(self, pg, mock_bot):
        """If geocoding failed for a home, broadcast must still deliver it to
        a radius-filtered sub (skip the check rather than silently drop)."""
        _seed_target(pg)

        sub_near_only = 333
        _insert_subscriber(
            pg, telegram_id=sub_near_only,
            filter_radius_km=5.0, filter_center=AMSTERDAM,
        )

        with patch("hestia_utils.geocode.requests.get",
                   return_value=_pdok_empty()):
            db.add_home("http://x/noco", "Mystery Ln 9", "Amsterdam",
                        1500, "funda", datetime.now().isoformat())

        home_row = _fetch_home(pg, "http://x/noco")
        assert home_row["lat"] is None

        homes = [Home(address="Mystery Ln 9", city="Amsterdam",
                      url="http://x/noco", agency="funda", price=1500, sqm=-1)]

        import scraper
        with patch("hestia_utils.geocode.requests.get",
                   return_value=_pdok_empty()):
            self._run(scraper.broadcast(homes))

        sent = [c.kwargs for c in mock_bot.send_message.call_args_list]
        assert len(sent) == 1, "home without coords must not be dropped"
        assert sent[0]["chat_id"] == str(sub_near_only)
        assert "Mystery Ln 9" in sent[0]["text"]

    def test_set_filter_location_applied_against_live_db(self, pg, mock_bot):
        """db.set_filter_location writes the tuple; broadcast reads it back."""
        _seed_target(pg)

        telegram_id = 444
        _insert_subscriber(pg, telegram_id=telegram_id)
        chat = MagicMock()
        chat.id = telegram_id
        db.set_filter_location(chat, AMSTERDAM[0], AMSTERDAM[1], 5.0)

        # Sanity: the row we just wrote is what broadcast will see.
        conn = _pg_conn(pg)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT filter_center_lat, filter_center_lon, filter_radius_km "
                    "FROM hestia.subscribers WHERE telegram_id = %s",
                    [str(telegram_id)],
                )
                row = cur.fetchone()
        finally:
            conn.close()
        assert row["filter_center_lat"] == pytest.approx(AMSTERDAM[0])
        assert row["filter_radius_km"] == pytest.approx(5.0)

        pdok = _pdok_router({
            "Kerkstraat 1": AMSTERDAM,
            "Coolsingel 1": ROTTERDAM,
        })

        with patch("hestia_utils.geocode.requests.get", side_effect=pdok):
            db.add_home("http://s/near", "Kerkstraat 1", "Amsterdam",
                        1500, "funda", datetime.now().isoformat())
            db.add_home("http://s/far", "Coolsingel 1", "Rotterdam",
                        1500, "funda", datetime.now().isoformat())

        homes = [
            Home(address="Kerkstraat 1", city="Amsterdam",
                 url="http://s/near", agency="funda", price=1500, sqm=-1),
            Home(address="Coolsingel 1", city="Rotterdam",
                 url="http://s/far", agency="funda", price=1500, sqm=-1),
        ]

        import scraper
        with patch("hestia_utils.geocode.requests.get", side_effect=pdok):
            self._run(scraper.broadcast(homes))

        sent = [c.kwargs for c in mock_bot.send_message.call_args_list
                if c.kwargs.get("chat_id") == str(telegram_id)]
        assert len(sent) == 1
        assert "Kerkstraat 1" in sent[0]["text"]

        # And clearing the filter re-opens the subscriber to far listings.
        db.clear_filter_location(chat)
        mock_bot.send_message.reset_mock()
        with patch("hestia_utils.geocode.requests.get", side_effect=pdok):
            self._run(scraper.broadcast(homes))
        sent_after_clear = [c.kwargs for c in mock_bot.send_message.call_args_list
                            if c.kwargs.get("chat_id") == str(telegram_id)]
        assert len(sent_after_clear) == 2

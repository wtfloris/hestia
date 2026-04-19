"""Address geocoding for Dutch addresses via PDOK Locatieserver.

Results are cached in hestia.geocode_cache to avoid repeat PDOK calls for the
same address. Scrapers remain untouched; geocoding happens at DB-insert time
(see hestia_utils.db.add_home) and is best-effort — a miss stores NULL coords
so broadcast() can skip the radius check rather than dropping the home.
"""

import logging
import math
import re
from typing import Optional, Tuple

import requests

import hestia_utils.db as db


PDOK_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
PDOK_TIMEOUT = 5
MIN_SCORE = 7.0
USER_AGENT = "hestia-geocoder/1.0 (+https://hestia.bot)"

_UNIT_SUFFIX_RES = [
    re.compile(r"\s+\d+(?:hg|bg|vg)\s*$", re.IGNORECASE),   # "3hg", "2bg"
    re.compile(r"\s+[A-Z]\d+\s*$"),                          # "B2"
    re.compile(r"\s+(?:I{1,3}|IV|V|VI{1,3})\s*$"),           # Roman numerals for floor
    re.compile(r"\s+bis\s*$", re.IGNORECASE),                # NL addition
]
_POINT_RE = re.compile(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)")


def normalize_address(address: str) -> str:
    """Strip common unit/floor suffixes that PDOK doesn't know about.

    Only strips if the remainder still contains a house number digit, so we
    don't accidentally destroy the number itself.
    """
    if not address:
        return ""
    cleaned = re.sub(r"\s+", " ", address.strip())
    # One pass is enough for the suffixes we recognize.
    for pattern in _UNIT_SUFFIX_RES:
        candidate = pattern.sub("", cleaned).strip()
        if candidate != cleaned and re.search(r"\d", candidate):
            cleaned = candidate
            break
    return cleaned


def _parse_point(point_str: str) -> Optional[Tuple[float, float]]:
    """PDOK returns centroide_ll as 'POINT(lon lat)'. Returns (lat, lon)."""
    if not point_str:
        return None
    m = _POINT_RE.search(point_str)
    if not m:
        return None
    lon, lat = float(m.group(1)), float(m.group(2))
    return (lat, lon)


def _pdok_lookup(address: str, city: str, fq: str = "type:adres") -> Optional[Tuple[float, float, float]]:
    """Hit PDOK Locatieserver. Returns (lat, lon, score) or None."""
    query = f"{address} {city}".strip()
    if not query:
        return None
    try:
        r = requests.get(
            PDOK_URL,
            params={"q": query, "fq": fq, "rows": 1},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=PDOK_TIMEOUT,
        )
    except requests.RequestException as e:
        logging.warning(f"PDOK request failed for {query!r}: {repr(e)}")
        return None

    if r.status_code != 200:
        logging.warning(f"PDOK returned {r.status_code} for {query!r}")
        return None

    try:
        docs = r.json().get("response", {}).get("docs", [])
    except ValueError:
        logging.warning(f"PDOK returned non-JSON body for {query!r}")
        return None

    if not docs:
        return None

    top = docs[0]
    score = float(top.get("score", 0.0))
    coords = _parse_point(top.get("centroide_ll", ""))
    if coords is None:
        return None
    lat, lon = coords
    return (lat, lon, score)


def geocode(address: str, city: str) -> Optional[Tuple[float, float, float]]:
    """Resolve (address, city) to (lat, lon, confidence).

    Returns None if no usable result. Uses hestia.geocode_cache so repeat
    lookups are free. Confidence is PDOK's relevance score for the top hit
    (higher = more confident); 0.0 indicates a low-confidence fallback.
    """
    if not address:
        return None
    city = city or ""

    cached = db.fetch_one(
        "SELECT lat, lon, confidence FROM hestia.geocode_cache WHERE address = %s AND city = %s",
        [address, city],
    )
    if cached:
        if cached["lat"] is None or cached["lon"] is None:
            return None
        return (cached["lat"], cached["lon"], cached.get("confidence") or 0.0)

    normalized = normalize_address(address)
    result = _pdok_lookup(normalized, city, fq="type:adres")
    if result is None or result[2] < MIN_SCORE:
        fallback = _pdok_lookup(normalized, city, fq="type:weergavenaam")
        if fallback is not None and (result is None or fallback[2] > result[2]):
            result = (fallback[0], fallback[1], 0.0)

    if result is None:
        _store_cache(address, city, None, None, None)
        return None

    lat, lon, score = result
    _store_cache(address, city, lat, lon, score)
    return (lat, lon, score)


def _store_cache(address: str, city: str, lat, lon, confidence) -> None:
    db._write(
        """
        INSERT INTO hestia.geocode_cache (address, city, lat, lon, confidence, fetched_at)
        VALUES (%s, %s, %s, %s, %s, now())
        ON CONFLICT (address, city) DO UPDATE SET
            lat = EXCLUDED.lat,
            lon = EXCLUDED.lon,
            confidence = EXCLUDED.confidence,
            fetched_at = EXCLUDED.fetched_at
        """,
        [address, city, lat, lon, confidence],
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers between two WGS84 points."""
    r = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

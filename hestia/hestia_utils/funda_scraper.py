import json
import logging
from curl_cffi import requests
from hestia_utils.parser import Home, HomeResults

logger = logging.getLogger("funda")

# Akamai fingerprints the TLS handshake, and plain requests/urllib3 gets scored
# as a bot no matter how browser-like the headers are: pinning the cipher list
# bought a few days before the fingerprint was flagged durably. curl_cffi
# impersonates a real browser's handshake instead, and supplies the matching
# User-Agent itself. Profiles age as browsers ship, so if the 403s come back,
# bump this to a current one before reaching for anything more elaborate.
IMPERSONATE = "safari2601"


def scrape_funda(target: dict) -> list[Home]:
    headers = target.get("headers") or {}
    session = requests.Session(impersonate=IMPERSONATE)

    # Akamai wants either a bm_s cookie or the browser-ish headers off the
    # target; measured 8/8 with each on its own and 0/8 with neither, so the two
    # are redundant paths to the same 200. Prime for the cookie anyway and send
    # the headers too, so losing one to a rule change doesn't take the scraper
    # down with it. (ak_bmsc and bm_so come along with bm_s but neither works.)
    prime_url = headers.get("Referer", "https://www.funda.nl/")
    prime = session.get(
        prime_url,
        headers={"Accept-Language": headers.get("Accept-Language", "nl-NL,nl;q=0.9,en;q=0.8")},
        timeout=30,
    )
    if prime.status_code != 200:
        raise ConnectionError(f"Got a non-OK status code priming the session: {prime.status_code}")

    # Drop the target's User-Agent: the impersonation profile sets one that
    # matches its handshake, and sending a second, possibly stale one over the
    # top is exactly the inconsistency the bot scoring looks for.
    search_headers = {k: v for k, v in headers.items() if k.lower() != "user-agent"}

    # The search endpoint is Elasticsearch _msearch, so the body is NDJSON.
    post_data = "\n".join(json.dumps(obj, separators=(",", ":")) for obj in target["post_data"]) + "\n"
    r = session.post(target["queryurl"], data=post_data, headers=search_headers, timeout=30)

    if r.status_code != 200:
        raise ConnectionError(f"Got a non-OK status code: {r.status_code}")

    return list(HomeResults("funda", r))

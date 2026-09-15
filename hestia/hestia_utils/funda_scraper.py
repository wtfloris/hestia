import json
import logging
from curl_cffi import requests
from hestia_utils.parser import Home, HomeResults

logger = logging.getLogger("funda")

# Akamai fingerprints the TLS handshake, and plain requests/urllib3 gets scored
# as a bot no matter how browser-like the headers are: pinning the cipher list
# bought a few days before the fingerprint was flagged durably. curl_cffi
# impersonates a real browser's handshake instead. Keep this in step with the
# User-Agent on the target so the handshake and the headers tell the same story.
IMPERSONATE = "safari2601"


def scrape_funda(target: dict) -> list[Home]:
    headers = target.get("headers") or {}
    session = requests.Session(impersonate=IMPERSONATE)

    # Akamai only serves the search API to clients holding a bm_s cookie, which
    # is handed out by the public site, so prime the session before searching.
    # (ak_bmsc and bm_so come along with it but neither is sufficient alone.)
    prime_url = headers.get("Referer", "https://www.funda.nl/")
    prime = session.get(
        prime_url,
        headers={"Accept-Language": headers.get("Accept-Language", "nl-NL,nl;q=0.9,en;q=0.8")},
        timeout=30,
    )
    if prime.status_code != 200:
        raise ConnectionError(f"Got a non-OK status code priming the session: {prime.status_code}")

    # The impersonation profile supplies its own User-Agent; sending the one off
    # the target too would risk it drifting out of step with the handshake.
    search_headers = {k: v for k, v in headers.items() if k.lower() != "user-agent"}

    # The search endpoint is Elasticsearch _msearch, so the body is NDJSON.
    post_data = "\n".join(json.dumps(obj, separators=(",", ":")) for obj in target["post_data"]) + "\n"
    r = session.post(target["queryurl"], data=post_data, headers=search_headers, timeout=30)

    if r.status_code != 200:
        raise ConnectionError(f"Got a non-OK status code: {r.status_code}")

    return list(HomeResults("funda", r))

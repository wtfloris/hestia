import json
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from hestia_utils.parser import Home, HomeResults

logger = logging.getLogger("funda")

# urllib3 2.x reordered the default cipher list, which gives us a TLS handshake
# fingerprint Akamai answers with a 403 even when cookies and headers are all
# correct. Pinning the classic ordering makes the handshake look like a browser's.
CIPHERS = (
    "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:"
    "ECDH+AESGCM:DH+AESGCM:ECDH+AES:DH+AES:RSA+AESGCM:RSA+AES:"
    "!aNULL:!eNULL:!MD5:!DSS"
)


class _TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = create_urllib3_context(ciphers=CIPHERS)
        return super().init_poolmanager(*args, **kwargs)


def scrape_funda(target: dict) -> list[Home]:
    headers = target.get("headers") or {}
    session = requests.Session()
    session.mount("https://", _TLSAdapter())

    # Akamai only serves the search API to clients holding a bm_s cookie, which
    # is handed out by the public site, so prime the session before searching.
    # (ak_bmsc and bm_so come along with it but neither is sufficient alone.)
    prime_url = headers.get("Referer", "https://www.funda.nl/")
    prime = session.get(
        prime_url,
        headers={
            "User-Agent": headers.get("User-Agent", ""),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": headers.get("Accept-Language", "nl-NL,nl;q=0.9,en;q=0.8"),
        },
        timeout=30,
    )
    if prime.status_code != 200:
        raise ConnectionError(f"Got a non-OK status code priming the session: {prime.status_code}")

    # The search endpoint is Elasticsearch _msearch, so the body is NDJSON.
    post_data = "\n".join(json.dumps(obj, separators=(",", ":")) for obj in target["post_data"]) + "\n"
    r = session.post(target["queryurl"], data=post_data, headers=headers, timeout=30)

    if r.status_code != 200:
        raise ConnectionError(f"Got a non-OK status code: {r.status_code}")

    return list(HomeResults("funda", r))

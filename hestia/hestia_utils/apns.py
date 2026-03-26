import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
try:
    import jwt
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    jwt = None

import hestia_utils.secrets as secrets


logger = logging.getLogger(__name__)

_TRANSIENT_HTTP_STATUSES = {429, 500, 502, 503, 504}
_PERMANENT_REASONS = {
    "BadDeviceToken",
    "DeviceTokenNotForTopic",
    "Unregistered",
}


@dataclass
class APNsSendResult:
    ok: bool
    should_retry: bool = False
    permanent_invalid: bool = False
    reason: str = ""
    status_code: int = 0


def _is_configured() -> bool:
    if jwt is None:
        return False
    apns_cfg = getattr(secrets, "APNS", None)
    if not isinstance(apns_cfg, dict):
        return False
    required = ["team_id", "key_id", "bundle_id", "private_key", "use_sandbox"]
    return all(apns_cfg.get(k) for k in required[:-1]) and ("use_sandbox" in apns_cfg)


class APNsClient:
    """Minimal APNs HTTP/2 client using token-based auth."""

    def __init__(self):
        self._bearer_token = ""
        self._bearer_expiry_epoch = 0

    @property
    def enabled(self) -> bool:
        return _is_configured()

    def _build_jwt(self) -> str:
        now = int(time.time())
        apns_cfg = secrets.APNS
        payload = {
            "iss": apns_cfg["team_id"],
            "iat": now,
        }
        headers = {
            "alg": "ES256",
            "kid": apns_cfg["key_id"],
        }
        token = jwt.encode(
            payload=payload,
            key=apns_cfg["private_key"],
            algorithm="ES256",
            headers=headers,
        )
        # APNs requires token refresh at most every 60m; refresh a bit early.
        self._bearer_expiry_epoch = now + (50 * 60)
        return token

    def _get_bearer_token(self) -> str:
        now = int(time.time())
        if self._bearer_token and now < self._bearer_expiry_epoch:
            return self._bearer_token
        self._bearer_token = self._build_jwt()
        return self._bearer_token

    def _base_url(self) -> str:
        return "https://api.sandbox.push.apple.com" if secrets.APNS["use_sandbox"] else "https://api.push.apple.com"

    def send(self, apns_token: str, payload: dict) -> APNsSendResult:
        if not self.enabled:
            return APNsSendResult(ok=False, reason="APNS disabled")

        headers = {
            "authorization": f"bearer {self._get_bearer_token()}",
            "apns-topic": secrets.APNS["bundle_id"],
            "apns-push-type": "alert",
            "content-type": "application/json",
        }
        url = f"{self._base_url()}/3/device/{apns_token}"
        try:
            with httpx.Client(http2=True, timeout=10) as client:
                r = client.post(url, headers=headers, content=json.dumps(payload))
        except httpx.RequestError as e:
            logger.warning("APNs request failed: %r", e)
            return APNsSendResult(ok=False, should_retry=True, reason=repr(e))

        if r.status_code == 200:
            return APNsSendResult(ok=True, status_code=200)

        reason = ""
        try:
            reason = (r.json() or {}).get("reason", "")
        except ValueError:
            reason = ""

        permanent_invalid = reason in _PERMANENT_REASONS
        should_retry = (r.status_code in _TRANSIENT_HTTP_STATUSES) or (reason == "TooManyRequests")

        return APNsSendResult(
            ok=False,
            should_retry=should_retry,
            permanent_invalid=permanent_invalid,
            reason=reason,
            status_code=r.status_code,
        )


def build_home_notification_payload(home, agency_name: str) -> dict:
    if home.sqm > 0:
        body = f"€{home.price}/m, {home.sqm} m²"
    else:
        body = f"€{home.price}/m"

    now_utc = datetime.now(timezone.utc).isoformat()
    return {
        "aps": {
            "alert": {
                "title": f"{re.sub(r'\s*\[€\d+\]$', '', home.address)}, {home.city}",
                "body": body,
            },
            "sound": "default",
        },
        "home_url": home.url,
        "agency": agency_name,
        "sent_at": now_utc,
    }

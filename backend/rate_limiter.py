"""Shared slowapi limiter (AD-44).

FPRM-460 / AD-46 — proxy-aware client keying. Behind Railway's edge proxy the
TCP peer (``request.client.host``, which ``get_remote_address`` returns) is the
proxy, and Railway routes successive requests from rotating internal source
addresses, so the per-IP limit landed every request in a *different* bucket and
never accumulated — zero 429s in production even though CI was green (the test
``TestClient`` keeps a single stable peer). We key on the real external client
IP reported by the trusted edge proxy instead.

Forgery posture: ``X-Envoy-External-Address`` is set by Railway's Envoy edge to
the observed external client and is overwritten on every hop, so a client cannot
forge it to rotate keys (bypass) or pin it to a victim (targeted DoS). We prefer
it; only when it is absent (non-Railway / direct hits) do we fall back to the
left-most ``X-Forwarded-For`` entry, and finally to the TCP peer. Every candidate
is validated as a real IP before use so a garbage header can't create odd keys.
"""
import ipaddress

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        return None


def get_client_ip(request: Request) -> str:
    """Resolve the rate-limit key to the real external client IP behind a proxy."""
    # 1) Railway/Envoy edge — single, proxy-controlled, non-forgeable client IP.
    envoy = _valid_ip(request.headers.get("X-Envoy-External-Address"))
    if envoy:
        return envoy
    # 2) Standard proxy chain — the left-most hop is the original client.
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        first = _valid_ip(xff.split(",")[0])
        if first:
            return first
    # 3) Direct connection (local dev, tests, non-proxied) — the TCP peer.
    return get_remote_address(request)


# headers_enabled=True surfaces X-RateLimit-Limit/Remaining/Reset on limited
# routes and a Retry-After on the 429 — so operators (and the FPRM-460 live
# verification) can confirm the control is actually engaging in production.
limiter = Limiter(key_func=get_client_ip, headers_enabled=True)

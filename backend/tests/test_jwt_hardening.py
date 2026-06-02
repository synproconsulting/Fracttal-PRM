"""Sprint 25 PR A / FPRM-452 — JWT validation hardening (algorithm pinning).

`decode_access_token` pins `algorithms=[JWT_ALGORITHM]`, so an `alg:none` token
and a token signed with a different algorithm are both rejected, while a normally
issued token still validates.
"""
import base64
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jwt
import pytest
from fastapi import HTTPException

from auth import create_access_token, decode_access_token, JWT_SECRET, JWT_ALGORITHM


def _b64url(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def test_normal_token_validates():
    tok = create_access_token({"sub": str(uuid.uuid4()), "role": "system_admin"})
    payload = decode_access_token(tok)
    assert payload["role"] == "system_admin"


def test_alg_none_token_rejected():
    # Hand-built unsigned JWT with header alg=none and an empty signature segment.
    forged = _b64url({"alg": "none", "typ": "JWT"}) + "." + \
        _b64url({"sub": str(uuid.uuid4()), "role": "system_admin"}) + "."
    with pytest.raises(HTTPException) as exc:
        decode_access_token(forged)
    assert exc.value.status_code == 401


def test_different_algorithm_rejected():
    # Same secret but a different HMAC algorithm than the pinned one — must be
    # rejected because the header alg (HS512) is not in the allowed list.
    other_alg = "HS512" if JWT_ALGORITHM != "HS512" else "HS256"
    other = jwt.encode({"sub": str(uuid.uuid4())}, JWT_SECRET, algorithm=other_alg)
    with pytest.raises(HTTPException) as exc:
        decode_access_token(other)
    assert exc.value.status_code == 401

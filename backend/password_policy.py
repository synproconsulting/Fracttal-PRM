"""Sprint 25 PR B / FPRM-456 — server-side password-strength policy.

One shared validator used by every password-set / password-reset path so the
policy is enforced in exactly one place. Baseline policy: minimum length 12 plus
complexity (uppercase + lowercase + digit). A symbol is recommended but not
required, so the documented test credential ``TestPass123!`` (12 chars, mixed
case, digit, symbol) and ``PartnerPass123!`` satisfy it.

Raises HTTP 422 with a clear message on a weak password — never logs or echoes
the password itself.
"""
import re

from fastapi import HTTPException, status

MIN_LENGTH = 12


def validate_password_strength(password: str) -> None:
    """Raise HTTPException(422) if ``password`` fails the baseline policy."""
    missing = []
    if not password or len(password) < MIN_LENGTH:
        missing.append(f"at least {MIN_LENGTH} characters")
    if not re.search(r"[A-Z]", password or ""):
        missing.append("an uppercase letter")
    if not re.search(r"[a-z]", password or ""):
        missing.append("a lowercase letter")
    if not re.search(r"\d", password or ""):
        missing.append("a digit")
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain " + ", ".join(missing) + ".",
        )

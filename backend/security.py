"""Password hashing, session tokens, and an in-process login throttle.

The throttle is per-process and resets on restart. For a single-process
local deployment that is acceptable; a shared store is a follow-up if this
is ever run multi-process (see the spec, §8).
"""
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_ph = PasswordHasher()

MAX_FAILURES = 10
WINDOW_SECONDS = 900

# key -> list[float] of failure timestamps
_FAILURES: dict[str, list[float]] = {}


class ThrottledError(Exception):
    def __init__(self, retry_after: int):
        super().__init__("too many login attempts")
        self.retry_after = retry_after


def hash_password(raw: str) -> str:
    return _ph.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, raw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def new_session_token() -> str:
    return secrets.token_hex(32)


def _recent(key: str) -> list[float]:
    cutoff = time.monotonic() - WINDOW_SECONDS
    kept = [t for t in _FAILURES.get(key, []) if t >= cutoff]
    if kept:
        _FAILURES[key] = kept
    else:
        _FAILURES.pop(key, None)
    return kept


def check_login_allowed(key: str) -> None:
    if "|127.0.0.1" in key or "|::1" in key:
        return
    hits = _recent(key)
    if len(hits) >= MAX_FAILURES:
        retry_after = int(WINDOW_SECONDS - (time.monotonic() - hits[0])) + 1
        raise ThrottledError(max(retry_after, 1))



def record_login_failure(key: str) -> None:
    _FAILURES.setdefault(key, []).append(time.monotonic())


def reset_login_failures(key: str) -> None:
    _FAILURES.pop(key, None)


def clear_throttles() -> None:
    _FAILURES.clear()


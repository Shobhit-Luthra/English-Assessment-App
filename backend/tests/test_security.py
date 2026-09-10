import time

import pytest

import security


def test_hash_verify_round_trip():
    h = security.hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert security.verify_password("correct horse battery staple", h)
    assert not security.verify_password("wrong", h)


def test_new_session_token_is_unique_and_hex():
    a, b = security.new_session_token(), security.new_session_token()
    assert a != b
    assert len(a) == 64 and int(a, 16) >= 0


def test_throttle_trips_after_max_failures(monkeypatch):
    monkeypatch.setattr(security, "_FAILURES", {})
    key = "user@example.com|1.2.3.4"
    for _ in range(security.MAX_FAILURES):
        security.check_login_allowed(key)  # still allowed
        security.record_login_failure(key)
    with pytest.raises(security.ThrottledError) as ei:
        security.check_login_allowed(key)
    assert ei.value.retry_after > 0
    security.reset_login_failures(key)
    security.check_login_allowed(key)  # cleared

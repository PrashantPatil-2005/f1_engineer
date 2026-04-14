"""Direct tests for the token-bucket rate limiter."""

import time

import pytest

from app import routes


@pytest.fixture(autouse=True)
def _isolate_buckets():
    routes._rate_limits.clear()
    yield
    routes._rate_limits.clear()


def test_first_burst_within_limit_is_allowed():
    ip = "1.2.3.4"
    for _ in range(routes.RATE_LIMIT):
        assert routes._check_rate_limit(ip) is True


def test_exceeding_limit_is_rejected():
    ip = "1.2.3.4"
    for _ in range(routes.RATE_LIMIT):
        routes._check_rate_limit(ip)
    assert routes._check_rate_limit(ip) is False


def test_buckets_are_per_ip():
    assert routes._check_rate_limit("a") is True
    # Drain ip "b" — should not affect "a".
    for _ in range(routes.RATE_LIMIT):
        routes._check_rate_limit("b")
    assert routes._check_rate_limit("b") is False
    assert routes._check_rate_limit("a") is True


def test_refill_restores_tokens_after_window(monkeypatch):
    ip = "refill"
    # Drain.
    for _ in range(routes.RATE_LIMIT):
        routes._check_rate_limit(ip)
    assert routes._check_rate_limit(ip) is False

    # Fast-forward time by one full window.
    real_time = time.time
    fake_now = real_time() + routes.RATE_WINDOW + 1
    monkeypatch.setattr(routes.time, "time", lambda: fake_now)

    assert routes._check_rate_limit(ip) is True

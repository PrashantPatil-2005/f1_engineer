"""Validation tests for POST /api/ask.

These hit only the request-validation branches *before* the MCP/LLM pipeline
is exercised, so they don't need network or model access.
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_limiter(reset_rate_limiter):
    yield


def test_missing_body_returns_400(client):
    resp = client.post("/api/ask")
    assert resp.status_code == 400
    assert "Missing 'question'" in resp.get_json()["error"]


def test_missing_question_field_returns_400(client):
    resp = client.post("/api/ask", json={"foo": "bar"})
    assert resp.status_code == 400


def test_empty_question_returns_400(client):
    resp = client.post("/api/ask", json={"question": "   "})
    assert resp.status_code == 400
    assert "empty" in resp.get_json()["error"].lower()


def test_overlong_question_returns_400(client):
    resp = client.post("/api/ask", json={"question": "x" * 501})
    assert resp.status_code == 400
    assert "too long" in resp.get_json()["error"].lower()


def test_rate_limit_kicks_in_after_quota(client):
    from app import routes

    payload = {"question": "valid question"}
    # Drain the bucket directly to keep the test fast and avoid touching the
    # MCP pipeline. The next /ask call must be rejected with 429.
    for _ in range(routes.RATE_LIMIT):
        routes._check_rate_limit("127.0.0.1")
    resp = client.post("/api/ask", json=payload)
    assert resp.status_code == 429
    body = resp.get_json()
    assert "Rate limit" in body["error"]
    assert body["retry_after"] == routes.RATE_WINDOW

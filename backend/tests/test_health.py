"""Liveness and readiness endpoint tests."""


def test_health_is_cheap_and_always_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["service"] == "f1-engineer"


def test_ready_returns_structured_payload(client):
    resp = client.get("/api/ready")
    # Status code depends on the test environment's installed deps. Either way,
    # the payload shape must be stable so dashboards/alerts can rely on it.
    assert resp.status_code in (200, 503)
    body = resp.get_json()
    assert body["status"] in ("ready", "not_ready")
    assert "failing" in body
    assert "checks" in body
    assert "dependency_status" in body["checks"]
    assert "data_writable" in body["checks"]
    assert "groq_api_key_present" in body["checks"]


def test_ready_returns_503_when_config_error_present(app, client):
    app.config["CONFIG_ERROR"] = "synthetic config failure for test"
    resp = client.get("/api/ready")
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["status"] == "not_ready"
    assert "config" in body["failing"]
    assert body["config_error"] == "synthetic config failure for test"

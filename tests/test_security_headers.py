"""
Tests for the security headers on every response (spec PR-N2).
"""

from app.security import CDNJS, JSDELIVR


def test_pages_carry_the_security_headers(client):
    headers = client.get("/").headers

    assert "Content-Security-Policy" in headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in headers["Permissions-Policy"]


def test_the_policy_allows_only_the_sites_scripts_and_blocks_framing(client):
    policy = client.get("/").headers["Content-Security-Policy"]

    assert f"script-src 'self' {JSDELIVR} {CDNJS} 'wasm-unsafe-eval'" in policy
    assert "'unsafe-inline'" not in policy.split("script-src")[1].split(";")[0]
    assert "frame-ancestors 'none'" in policy
    assert "object-src 'none'" in policy


def test_json_responses_are_protected_too(client):
    headers = client.get("/health").headers

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in headers


def test_https_is_enforced_only_when_the_site_uses_https(app, client):
    assert "Strict-Transport-Security" not in client.get("/").headers

    app.config["SESSION_COOKIE_SECURE"] = True

    assert "max-age=31536000" in client.get("/").headers["Strict-Transport-Security"]
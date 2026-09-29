"""
Tests for the Privacy and Terms pages and the site-wide accessibility
helpers (spec section 10, NFR04).
"""

from app.services.guest import GUEST_RETENTION_DAYS


def visible_text(response):
    return " ".join(response.get_data(as_text=True).split())


def test_privacy_page_explains_what_is_stored_and_shared(client):
    response = client.get("/privacy")
    text = visible_text(response)

    assert response.status_code == 200
    assert "never receives your name, email address, or password" in text
    assert "Gemini" in text
    assert f"deleted after {GUEST_RETENTION_DAYS} days" in text


def test_terms_page_is_available(client):
    response = client.get("/terms")

    assert response.status_code == 200
    assert "Fair use" in visible_text(response)


def test_every_page_links_to_privacy_and_terms_in_the_footer(client):
    for path in ("/", "/challenges", "/leaderboard"):
        html = client.get(path).get_data(as_text=True)
        assert 'href="/privacy"' in html
        assert 'href="/terms"' in html


def test_every_page_has_a_skip_link_to_the_main_content(client):
    html = client.get("/").get_data(as_text=True)

    assert html.index('class="skip-link"') < html.index('class="site-header"')
    assert 'href="#main"' in html
    assert 'id="main"' in html
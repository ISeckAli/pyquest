"""
Tests for the styling pass: the mobile menu button and the theme
stylesheet's loading order.
"""


def test_the_header_has_an_accessible_menu_button(client):
    html = client.get("/").get_data(as_text=True)

    assert 'class="nav-toggle"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="nav-links"' in html
    assert 'id="nav-links"' in html
    assert "js/nav.js" in html


def test_the_theme_loads_after_each_pages_own_stylesheet(client):
    html = client.get("/leaderboard").get_data(as_text=True)

    assert html.index("css/leaderboard.css") < html.index("css/theme.css")


def test_every_page_gets_the_theme(client):
    for path in ("/", "/challenges", "/privacy"):
        assert "css/theme.css" in client.get(path).get_data(as_text=True)
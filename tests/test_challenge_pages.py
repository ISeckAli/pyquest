"""
Tests for the public challenge library and challenge pages (spec FR04,
PR-L1, and the rule that hidden tests and reference solutions never reach
the browser).
"""

import pytest

from app.services.challenges import add_test_case, create_challenge, create_topic, publish

# Distinctive strings that must never appear in a learner-facing page.
HIDDEN_INPUT = "HIDDEN-INPUT-123"
HIDDEN_OUTPUT = "HIDDEN-OUTPUT-456"
REFERENCE_MARKER = "REFERENCE-SOLUTION-MARKER"


def publish_new(topic, title, difficulty):
    """Create and publish a challenge with one visible and two hidden tests."""
    challenge = create_challenge(
        None, title, f"Solve {title}.", topic, difficulty,
        reference_solution=f"print('{REFERENCE_MARKER}')",
    )
    add_test_case(challenge, "abc", "cba", is_hidden=False)
    add_test_case(challenge, HIDDEN_INPUT, HIDDEN_OUTPUT, is_hidden=True)
    add_test_case(challenge, "zz", "zz", is_hidden=True)
    publish(challenge)
    return challenge


@pytest.fixture
def library(app):
    """Two published challenges in two topics, plus one unpublished draft."""
    strings = create_topic("Strings", "Working with text.", sort_order=1)
    loops = create_topic("Loops", sort_order=2)
    publish_new(strings, "Reverse a String", "beginner")
    publish_new(loops, "Count Up", "intermediate")
    create_challenge(None, "Secret Draft", "Not ready yet.", strings, "beginner")


def page(client, url):
    return client.get(url).get_data(as_text=True)


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

def test_library_is_open_to_visitors_and_hides_drafts(client, library):
    response = client.get("/challenges")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Reverse a String" in html
    assert "Count Up" in html
    assert "Secret Draft" not in html


def test_library_shows_topics_in_learning_path_order(client, library):
    html = page(client, "/challenges")

    assert html.index('id="topic-strings"') < html.index('id="topic-loops"')


@pytest.mark.parametrize(
    "url, shown, not_shown",
    [
        ("/challenges?topic=loops", "Count Up", "Reverse a String"),
        ("/challenges?difficulty=beginner", "Reverse a String", "Count Up"),
        ("/challenges?q=REVERSE", "Reverse a String", "Count Up"),
    ],
)
def test_library_filters(client, library, url, shown, not_shown):
    html = page(client, url)

    assert shown in html
    assert not_shown not in html


def test_unknown_filter_values_are_ignored(client, library):
    html = page(client, "/challenges?difficulty=expert")

    assert "Reverse a String" in html
    assert "Count Up" in html


def test_filter_form_remembers_the_search(client, library):
    assert 'value="rev"' in page(client, "/challenges?q=rev")


def test_empty_library_shows_a_message(client):
    assert "No challenges match" in page(client, "/challenges")


# ---------------------------------------------------------------------------
# Challenge page
# ---------------------------------------------------------------------------

def test_challenge_page_shows_problem_and_visible_example(client, library):
    html = page(client, "/challenges/reverse-a-string")

    assert "Solve Reverse a String." in html
    assert "cba" in html


def test_challenge_page_never_reveals_hidden_tests_or_solution(client, library):
    """The answers that make grading fair must never reach the browser."""
    html = page(client, "/challenges/reverse-a-string")

    assert HIDDEN_INPUT not in html
    assert HIDDEN_OUTPUT not in html
    assert REFERENCE_MARKER not in html


def test_unpublished_and_unknown_challenges_are_not_found(client, library):
    assert client.get("/challenges/secret-draft").status_code == 404
    assert client.get("/challenges/no-such-challenge").status_code == 404


def test_landing_page_links_to_the_library(client):
    assert 'href="/challenges"' in page(client, "/")
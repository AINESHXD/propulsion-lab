"""Methodology page contract, and the Classroom's removal from the live site.

This file used to be ``test_classroom.py`` and asserted that ``/classroom/``
served a page covering all five engine families. That contract was retired on
2026-08-05: five hand-written problems behind a top-level nav link promised a
teaching product that did not exist, so the page was archived under
``docs/archive/classroom/`` until the generated version is worth shipping.

What is asserted here is the *new* contract — the methodology page still states
its limits, and the Classroom is gone from the site but kept in the repo, with
restoration instructions, rather than deleted.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_STATIC = _ROOT / "app" / "static"
_ARCHIVE = _ROOT / "docs" / "archive" / "classroom"


def test_methodology_page_states_limits() -> None:
    html = (_STATIC / "methodology.html").read_text(encoding="utf-8").lower()
    # the key honesty claims a reviewer looks for
    assert "reduced-order" in html
    assert "not" in html and "claimed" in html
    assert "no manufacturer-level validation" in html
    assert "synthetic" in html  # maps are illustrative, not measured


def test_console_links_to_methodology() -> None:
    html = (_STATIC / "index.html").read_text(encoding="utf-8")
    assert "methodology.html" in html


def test_the_classroom_is_archived_not_deleted() -> None:
    # The point of pulling it was to stop advertising an unfinished feature,
    # not to throw the work away — the grading-against-the-real-solver design
    # is meant to survive into its replacement.
    assert (_ARCHIVE / "index.html").is_file()
    assert (_ARCHIVE / "classroom.js").is_file()
    notes = (_ARCHIVE / "README.md").read_text(encoding="utf-8")
    assert "How to restore it" in notes
    # The restore note is only useful if it names every place a link was cut.
    for page in ("index.html", "methodology.html", "m/index.html", "privacy.html"):
        assert page in notes, f"restore note does not mention {page}"


def test_no_page_still_links_to_the_classroom() -> None:
    # A nav entry pointing at a route that no longer exists is a 404 in the
    # main navigation, which is worse than the feature being missing.
    for page in ("index.html", "methodology.html", "privacy.html", "m/index.html"):
        html = (_STATIC / page).read_text(encoding="utf-8")
        assert "/classroom" not in html, f"{page} still links to the classroom"


def test_the_classroom_route_is_gone() -> None:
    source = (_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "/classroom" not in source
    assert "def classroom(" not in source

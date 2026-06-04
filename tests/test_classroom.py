"""Classroom (guided challenges) + methodology page: routes and contract.

The classroom grades answers client-side by calling the existing /simulate
endpoints, so these tests assert the route/page contract and that the embedded
challenges cover all five engine families. The physics endpoints themselves are
covered by their own tests.
"""

from __future__ import annotations

from pathlib import Path

from app.main import classroom

_ROOT = Path(__file__).resolve().parent.parent
_STATIC = _ROOT / "app" / "static"


def test_classroom_route_serves_index() -> None:
    response = classroom()
    assert Path(response.path).exists()
    assert Path(response.path).name == "index.html"
    assert Path(response.path).parent.name == "classroom"


def test_classroom_covers_all_five_engines() -> None:
    js = (_STATIC / "classroom" / "classroom.js").read_text(encoding="utf-8")
    for engine in ("Turbojet", "Turbofan", "Turboprop", "Ramjet", "Scramjet"):
        assert f'engine: "{engine}"' in js, f"missing challenge for {engine}"
    # each challenge points at a real simulate endpoint
    for ep in (
        "/simulate/turbojet", "/simulate/turbofan", "/simulate/turboprop",
        "/simulate/ramjet", "/simulate/scramjet",
    ):
        assert f'endpoint: "{ep}"' in js, f"missing endpoint {ep}"


def test_classroom_collects_nothing_and_is_honest() -> None:
    html = (_STATIC / "classroom" / "index.html").read_text(encoding="utf-8").lower()
    assert "<form" not in html  # no signup/account machinery
    assert "not a graded assessment" in html or "teaching exercises" in html


def test_methodology_page_states_limits() -> None:
    html = (_STATIC / "methodology.html").read_text(encoding="utf-8").lower()
    # the key honesty claims a reviewer looks for
    assert "reduced-order" in html
    assert "not" in html and "claimed" in html
    assert "no manufacturer-level validation" in html
    assert "synthetic" in html  # maps are illustrative, not measured


def test_console_links_to_classroom_and_methodology() -> None:
    html = (_STATIC / "index.html").read_text(encoding="utf-8")
    assert "/classroom/" in html
    assert "methodology.html" in html

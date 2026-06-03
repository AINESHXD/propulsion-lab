"""PistonLab — clean /piston/ route + static-page sanity checks.

PistonLab is the DAS LABS sibling console (reciprocating-engine air-standard
cycles). It ships client-side: a FastAPI route serves the page and the physics
lives in static JS, so these tests assert the route and the page/JS contract
rather than running the JS solver.
"""

from __future__ import annotations

from pathlib import Path

from app.main import piston_lab

_ROOT = Path(__file__).resolve().parent.parent
_PISTON = _ROOT / "app" / "static" / "piston"


def test_piston_route_serves_existing_index() -> None:
    response = piston_lab()
    assert Path(response.path).exists()
    assert Path(response.path).name == "index.html"
    assert Path(response.path).parent.name == "piston"


def test_piston_page_is_honest_and_collects_nothing() -> None:
    html = (_PISTON / "index.html").read_text(encoding="utf-8").lower()
    # No payment / account machinery on this page.
    assert "<form" not in html
    for processor in ("stripe", "paypal", "razorpay", "add to cart", "checkout"):
        assert processor not in html
    # It plainly states the air-standard idealisation rather than overclaiming.
    assert "air-standard" in html
    assert "ideal" in html


def test_piston_js_exports_the_solver_surface() -> None:
    js = (_PISTON / "piston.js").read_text(encoding="utf-8")
    for symbol in (
        "export function solveCycle",
        "export function closedFormEfficiency",
        "export function enginePerformance",
        "export function startPiston",
    ):
        assert symbol in js, f"missing {symbol}"
    # The three air-standard cycles must all be handled.
    for cycle in ('"otto"', '"diesel"', '"dual"'):
        assert cycle in js


def test_piston_assets_referenced_exist() -> None:
    # The page references its own CSS/JS under the static mount and the shared
    # wordmark asset; all must be present so the page renders standalone.
    assert (_PISTON / "piston.css").exists()
    assert (_PISTON / "piston.js").exists()
    assert (_ROOT / "app" / "static" / "assets" / "pistonlab_wordmark.png").exists()


def test_portal_still_shows_pistonlab_as_coming_soon() -> None:
    # PistonLab is built but NOT launched: the portal must still gate it.
    portal = (_ROOT / "app" / "static" / "portal.html").read_text(encoding="utf-8").lower()
    assert "coming soon" in portal
    # And it must not yet link the live /piston/ console from the portal card.
    assert 'href="/piston' not in portal

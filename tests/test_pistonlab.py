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
    for processor in ("stripe", "paypal", "razorpay", "add to cart", "checkout", "password"):
        assert processor not in html
    # The console is now wired to the crank-angle solver, and stays honest about
    # being a reduced-order model rather than a dyno reading.
    assert "crank-angle" in html
    assert "model estimates" in html
    assert "not measurements" in html


def test_piston_js_is_the_solver_api_client() -> None:
    js = (_PISTON / "piston.js").read_text(encoding="utf-8")
    # The console is a thin client on the Python solver, not a client-side
    # physics engine: it boots via startPiston and POSTs to the API.
    assert "export function startPiston" in js
    assert "/piston/simulate" in js
    assert "/piston/sweep" in js


def test_piston_assets_referenced_exist() -> None:
    # The page references its own CSS/JS under the static mount and the shared
    # wordmark asset; all must be present so the page renders standalone.
    assert (_PISTON / "piston.css").exists()
    assert (_PISTON / "piston.js").exists()
    assert (_ROOT / "app" / "static" / "assets" / "pistonlab_wordmark.png").exists()


def test_portal_presents_pistonlab_as_launched() -> None:
    # PistonLab is launched: the portal links it and no longer gates it. This
    # replaces the pre-launch check that asserted the opposite.
    portal = (_ROOT / "app" / "static" / "portal.html").read_text(encoding="utf-8")
    assert 'href="/piston/"' in portal
    lowered = portal.lower()
    assert "coming soon" not in lowered
    assert "in development" not in lowered
    # Both cards now carry the live treatment, so neither is the disabled variant.
    assert 'aria-disabled="true"' not in lowered
    assert 'class="card live piston"' in lowered


def test_both_labs_are_reachable_from_the_portal() -> None:
    portal = (_ROOT / "app" / "static" / "portal.html").read_text(encoding="utf-8")
    assert 'href="/lab/"' in portal        # PropulsionLab
    assert 'href="/piston/"' in portal     # PistonLab


def test_the_console_no_longer_wears_a_dev_badge() -> None:
    html = (_PISTON / "index.html").read_text(encoding="utf-8")
    assert "badge-dev" not in html


def test_the_piston_api_is_published() -> None:
    # At launch the endpoints join the public schema, the way PropulsionLab's are.
    from app.main import app

    paths = {r.path for r in app.routes}
    assert "/piston/simulate" in paths
    assert "/piston/sweep" in paths
    schema_paths = set(app.openapi()["paths"])
    assert "/piston/simulate" in schema_paths
    assert "/piston/sweep" in schema_paths

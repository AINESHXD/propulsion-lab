"""Mobile: the /m route, serving the phone console.

The phone console is a ground-up build under ``app/static/m/`` (its own
HTML/CSS/JS), not a responsive squeeze of the desktop page, and it is a thin
client on the same SI solver.

It was gated behind a holding notice on 2026-08-08 because it was not good
enough to be the first thing a launch visitor opened on a phone, and un-gated
on 2026-10-07 once it was: measured across six phone viewports from 320px to
430px wide plus landscape, it no longer scrolls sideways, nothing renders below
11px, and every control except one inline link clears a 44px touch target.

The notice is preserved at ``m/holding.html`` rather than deleted, so re-gating
is the same rename in reverse. These tests therefore assert both that the live
console is intact and that the escape route back is still there and still
honest.
"""

from __future__ import annotations

import asyncio
import re
import types
from pathlib import Path

from app.main import cache_control, mobile_console

_ROOT = Path(__file__).resolve().parent.parent
_M = _ROOT / "app" / "static" / "m"
_CONSOLE = (_M / "index.html").read_text(encoding="utf-8")
_HOLDING = (_M / "holding.html").read_text(encoding="utf-8")
_CSS = (_M / "mobile.css").read_text(encoding="utf-8")


class _Resp:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}


def _run_middleware(path: str, query: str = "") -> _Resp:
    """Drive the cache_control middleware with a fake request/response."""

    request = types.SimpleNamespace(url=types.SimpleNamespace(path=path, query=query))
    response = _Resp()

    async def call_next(_req):  # noqa: ANN001 - test stub
        return response

    return asyncio.run(cache_control(request, call_next))


# --------------------------------------------------------------------------- #
# routing and caching
# --------------------------------------------------------------------------- #
def test_m_route_serves_the_mobile_index() -> None:
    response = mobile_console()
    assert Path(response.path).exists()
    assert Path(response.path).name == "index.html"


def test_m_html_is_no_cache() -> None:
    # The console's HTML carries the ?v= tokens for its own CSS and JS. A
    # cached copy of this page points a returning visitor at a stale
    # stylesheet, which is how a phone build breaks for exactly the people who
    # have seen it before.
    assert _run_middleware("/m").headers["Cache-Control"] == "no-cache, must-revalidate"
    assert _run_middleware("/m/").headers["Cache-Control"] == "no-cache, must-revalidate"


def test_m_versioned_assets_are_immutable() -> None:
    headers = _run_middleware("/lab/m/mobile.css", "v=20261007-tap44").headers
    assert headers["Cache-Control"] == "public, max-age=31536000, immutable"


# --------------------------------------------------------------------------- #
# phones reach the console, and nobody is trapped on it
# --------------------------------------------------------------------------- #
def test_both_consoles_redirect_phones_to_m() -> None:
    # Gating one lab and not the other was an inconsistency when the notice
    # stood here, and it would be one now: a phone should reach the phone
    # build from either lab. The ?nomobile escape hatch stops that being a
    # dead end for anyone who wants the desktop console anyway.
    for page in ("index.html", "piston/index.html"):
        html = (_ROOT / "app" / "static" / page).read_text(encoding="utf-8")
        assert "/m" in html, page
        assert "nomobile" in html, page


def test_the_redirect_catches_a_phone_held_sideways() -> None:
    # Width alone missed landscape: an 844x390 handset is 844 wide, so it
    # sailed past a max-width gate and got the desktop console in a 390px-tall
    # window. The second query is a short viewport on a touch device, which is
    # a phone on its side and not a short desktop window.
    for page in ("index.html", "piston/index.html"):
        html = (_ROOT / "app" / "static" / page).read_text(encoding="utf-8")
        assert "max-height: 500px" in html, page
        assert "pointer: coarse" in html, page


def test_the_console_offers_a_way_to_the_desktop_build() -> None:
    assert "nomobile=1" in _CONSOLE


# --------------------------------------------------------------------------- #
# the live console
# --------------------------------------------------------------------------- #
def test_the_console_loads_its_own_client() -> None:
    assert "mobile.css?v=" in _CONSOLE
    assert "mobile.js?v=" in _CONSOLE


def test_the_console_is_a_thin_client_on_the_real_solver() -> None:
    js = (_M / "mobile.js").read_text(encoding="utf-8")
    for engine in ("turbojet", "turbofan", "turboprop", "ramjet", "scramjet"):
        assert f"/simulate/{engine}" in js, engine
        assert f"/simulate/{engine}/sweep" in js, engine
    assert "UNIT_DEFS" in js
    assert "224.808943" in js  # kN -> lbf factor, identical to app.js


def test_nothing_renders_below_eleven_pixels() -> None:
    # Engine codes and unit suffixes were 9px before un-gating. Anything under
    # about 11px stops being readable at arm's length on a phone, and this is
    # the regression guard on that: the hierarchy can stay, the floor cannot
    # move back down.
    too_small = [
        float(m) for m in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", _CSS)
        if float(m) < 11.0
    ]
    assert not too_small, f"phone text below 11px: {sorted(set(too_small))}"


def test_the_touch_controls_clear_forty_four_pixels() -> None:
    # Measured in a real browser at six phone sizes; asserted here on the rules
    # that produce it so a future edit cannot quietly shrink them again.
    for selector, declaration in (
        (".m-tab", "height: 44px"),
        (".m-menu-btn", "width: 44px; height: 44px"),
        (".m-units", "height: 44px"),
        (".m-sheet-close", "width: 44px; height: 44px"),
        (".m-preset", "min-height: 44px"),
        (".m-brand", "min-height: 44px"),
    ):
        # (?![\w-]) stops .m-brand matching .m-brand-text and .m-tab matching .m-tabs.
        block = re.search(rf"{re.escape(selector)}(?![\w-])\s*\{{(.*?)\}}", _CSS, re.DOTALL)
        assert block, f"{selector} rule missing"
        assert declaration in block.group(1), f"{selector} no longer clears 44px"


# --------------------------------------------------------------------------- #
# re-gating stays a rename
# --------------------------------------------------------------------------- #
def test_the_holding_notice_is_preserved() -> None:
    assert (_M / "holding.html").exists(), "re-gating must stay a rename"
    low = _HOLDING.lower()
    assert "in development" in low
    assert "rebuilt" in low or "being worked on" in low


def test_the_holding_notice_still_does_not_claim_an_outage() -> None:
    # If it is ever put back, it must still read as "this one build is being
    # worked on", not as "the site is down".
    low = _HOLDING.lower()
    for wrong in ("offline", "unavailable", "maintenance", "coming soon", "down for"):
        assert wrong not in low, f"the notice implies the site is down: {wrong!r}"
    assert "live" in low


def test_the_holding_notice_cannot_break_itself() -> None:
    # Self-contained on purpose: a holding page that depends on the console's
    # stylesheet or client can fail the same way the thing it stands in for
    # failed. Comments are stripped first, because what matters is what the
    # browser loads, not what the source mentions in prose.
    markup = re.sub(r"<!--.*?-->", "", _HOLDING, flags=re.DOTALL)
    assert "mobile.css" not in markup
    assert "mobile.js" not in markup
    assert "fetch(" not in markup
    assert "<script" not in markup
    assert 'rel="stylesheet"' not in markup


def test_nothing_under_m_collects_anything_sensitive() -> None:
    for page in ("index.html", "holding.html"):
        html = (_M / page).read_text(encoding="utf-8").lower()
        for processor in ("stripe", "paypal", "razorpay", "add to cart", "checkout", "password"):
            assert processor not in html, page

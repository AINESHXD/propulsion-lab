"""Mobile: the /m route, currently gated behind a development notice.

The phone console is a ground-up build under ``app/static/m/`` (its own
HTML/CSS/JS), not a responsive squeeze of the desktop page, and it is a thin
client on the same SI solver. It was gated on 2026-08-08 because it was not
considered good enough to be the first thing a launch visitor opened on a
phone. The console itself is preserved at ``m/console.html`` and still works;
restoring it is a rename.

So these now assert two things at once: that the gate is honest and does not
trap anyone, and that the console it replaced is intact and ready to come back.
"""

from __future__ import annotations

import asyncio
import re
import types
from pathlib import Path

from app.main import cache_control, mobile_console

_ROOT = Path(__file__).resolve().parent.parent
_M = _ROOT / "app" / "static" / "m"
_GATE = (_M / "index.html").read_text(encoding="utf-8")


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
# routing and caching, unchanged by the gate
# --------------------------------------------------------------------------- #
def test_m_route_serves_the_mobile_index() -> None:
    response = mobile_console()
    assert Path(response.path).exists()
    assert Path(response.path).name == "index.html"
    assert Path(response.path).parent.name == "m"


def test_m_html_is_no_cache() -> None:
    # Guards the stale-HTML class of bug that broke the first mobile attempt.
    # It matters more while gated, not less: when the console comes back, a
    # cached notice page would keep telling visitors it is still down.
    for path in ("/m", "/m/"):
        resp = _run_middleware(path)
        assert resp.headers.get("Cache-Control") == "no-cache, must-revalidate", path


def test_m_versioned_assets_are_immutable() -> None:
    for asset in ("/lab/m/mobile.css", "/lab/m/mobile.js"):
        resp = _run_middleware(asset, "v=20260620-m1")
        assert "immutable" in resp.headers.get("Cache-Control", ""), asset


def test_both_consoles_redirect_phones_to_m() -> None:
    # The redirect is what routes phones to the notice, and it has to cover
    # *both* labs: gating one while the other still serves a phone the full
    # console is not a gate, it is an inconsistency. PistonLab additionally had
    # a 93px horizontal overflow on a phone, so it was the worse of the two to
    # leave open. The ?nomobile escape hatch stops either being a dead end.
    for page in ("index.html", "piston/index.html"):
        html = (_ROOT / "app" / "static" / page).read_text(encoding="utf-8")
        assert 'location.replace("/m")' in html, page
        assert "nomobile" in html, page
        assert "max-width: 760px" in html, page


def test_the_redirect_fires_before_anything_renders() -> None:
    # A redirect that runs after the stylesheet and client have loaded shows a
    # flash of the very console being gated.
    for page in ("index.html", "piston/index.html"):
        html = (_ROOT / "app" / "static" / page).read_text(encoding="utf-8")
        redirect_at = html.index('location.replace("/m")')
        for asset in ("<body", 'rel="stylesheet"'):
            if asset in html:
                assert redirect_at < html.index(asset), f"{page}: redirect runs after {asset}"


# --------------------------------------------------------------------------- #
# the gate must be honest, and must not trap anyone
# --------------------------------------------------------------------------- #
def test_the_gate_says_it_is_in_development() -> None:
    low = _GATE.lower()
    assert "in development" in low
    assert "rebuilt" in low or "being worked on" in low


def test_the_gate_does_not_claim_the_labs_are_down() -> None:
    # The site is live; only the phone console is gated. A notice that reads
    # like an outage would cost more than the rough console ever did.
    low = _GATE.lower()
    for wrong in ("offline", "unavailable", "maintenance", "coming soon", "down for"):
        assert wrong not in low, f"the gate implies the site is down: {wrong!r}"
    assert "live" in low


def test_the_gate_leaves_a_way_through() -> None:
    # Nothing is blocked; the desktop console is still reachable from a phone.
    assert "/lab?nomobile=1" in _GATE
    assert 'href="/"' in _GATE
    # And it points at the pages that genuinely do read well on a phone.
    assert "/validation/" in _GATE


def test_the_gate_cannot_break_itself() -> None:
    # Self-contained on purpose: a holding page that depends on the console's
    # stylesheet or client, or on a fetch, can fail the same way the thing it
    # is standing in for failed.
    #
    # Comments are stripped first — what matters is what the browser actually
    # loads, not what the source happens to mention in prose.
    markup = re.sub(r"<!--.*?-->", "", _GATE, flags=re.DOTALL)
    assert "mobile.css" not in markup
    assert "mobile.js" not in markup
    assert "fetch(" not in markup
    # No external script or stylesheet at all: only inline <style>.
    assert "<script" not in markup
    assert 'rel="stylesheet"' not in markup


def test_the_gate_is_not_indexed() -> None:
    # It should not become the search result for the mobile console.
    assert 'name="robots"' in _GATE and "noindex" in _GATE


# --------------------------------------------------------------------------- #
# the gated console is preserved, not deleted
# --------------------------------------------------------------------------- #
def test_the_console_survives_the_gate() -> None:
    console = _M / "console.html"
    assert console.exists(), "the phone console must be restorable by rename"
    html = console.read_text(encoding="utf-8")
    assert "mobile.css?v=" in html
    assert "mobile.js?v=" in html


def test_the_preserved_console_is_still_a_thin_client() -> None:
    js = (_M / "mobile.js").read_text(encoding="utf-8")
    for engine in ("turbojet", "turbofan", "turboprop", "ramjet", "scramjet"):
        assert f"/simulate/{engine}" in js, engine
        assert f"/simulate/{engine}/sweep" in js, engine
    assert "UNIT_DEFS" in js
    assert "224.808943" in js  # kN -> lbf factor, identical to app.js


def test_nothing_under_m_collects_anything_sensitive() -> None:
    for page in ("index.html", "console.html"):
        html = (_M / page).read_text(encoding="utf-8").lower()
        for processor in ("stripe", "paypal", "razorpay", "add to cart", "checkout", "password"):
            assert processor not in html, page

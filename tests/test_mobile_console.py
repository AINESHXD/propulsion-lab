"""Mobile console — clean /m route, no-cache HTML, thin-client contract.

The mobile console is a ground-up phone build under ``app/static/m/`` (its own
HTML/CSS/JS), not a responsive squeeze of the desktop page. It is a thin client
on the same SI solver: it POSTs to ``/simulate/<engine>`` and
``/simulate/<engine>/sweep`` and reuses the same unit-display layer.

These tests assert the route + page contract (the physics itself is covered by
the engine-core and endpoint tests the mobile client calls into). We call the
handler / middleware directly so we do not pull in httpx as a test dependency,
matching the rest of the suite.
"""

from __future__ import annotations

import asyncio
import types
from pathlib import Path

from app.main import cache_control, mobile_console

_ROOT = Path(__file__).resolve().parent.parent
_M = _ROOT / "app" / "static" / "m"


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


def test_m_route_serves_mobile_index() -> None:
    response = mobile_console()
    assert Path(response.path).exists()
    assert Path(response.path).name == "index.html"
    assert Path(response.path).parent.name == "m"


def test_m_html_is_no_cache() -> None:
    # Guards the stale-HTML class of bug that broke the first mobile attempt:
    # a cached page that points at an old, broken CSS/JS token. Both the clean
    # and trailing-slash forms must revalidate.
    for path in ("/m", "/m/"):
        resp = _run_middleware(path)
        assert resp.headers.get("Cache-Control") == "no-cache, must-revalidate", path


def test_m_versioned_assets_are_immutable() -> None:
    # The page's own CSS/JS carry ?v= tokens, so they are safe to cache forever
    # (the URL changes whenever the file does).
    for asset in ("/lab/m/mobile.css", "/lab/m/mobile.js"):
        resp = _run_middleware(asset, "v=20260620-m1")
        assert "immutable" in resp.headers.get("Cache-Control", ""), asset


def test_mobile_assets_present_and_versioned() -> None:
    assert (_M / "mobile.css").exists()
    assert (_M / "mobile.js").exists()
    html = (_M / "index.html").read_text(encoding="utf-8")
    # Both assets are referenced with a cache-busting version token.
    assert "mobile.css?v=" in html
    assert "mobile.js?v=" in html


def test_desktop_console_redirects_phones_to_m() -> None:
    # The desktop console must send phones to /m before render, with a
    # ?nomobile escape hatch so the full console stays reachable on a phone.
    index = (_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'location.replace("/m")' in index
    assert "nomobile" in index
    assert "max-width: 760px" in index


def test_mobile_js_is_a_thin_client_on_the_real_solver() -> None:
    js = (_M / "mobile.js").read_text(encoding="utf-8")
    # Every engine family routes to the same SI endpoints the desktop uses.
    for engine in ("turbojet", "turbofan", "turboprop", "ramjet", "scramjet"):
        assert f"/simulate/{engine}" in js, engine
        assert f"/simulate/{engine}/sweep" in js, engine
    # It reuses the same display-unit layer (SI solver, US is display-only).
    assert "UNIT_DEFS" in js
    assert "224.808943" in js  # kN -> lbf factor, identical to app.js


def test_mobile_page_collects_nothing_sensitive() -> None:
    # A console legitimately has an input form; what it must NOT have is any
    # payment / account machinery.
    html = (_M / "index.html").read_text(encoding="utf-8").lower()
    for processor in ("stripe", "paypal", "razorpay", "add to cart", "checkout", "password"):
        assert processor not in html

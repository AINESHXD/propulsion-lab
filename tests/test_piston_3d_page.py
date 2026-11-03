"""The PistonLab 3D page and the contract it relies on.

The page is a single HTML file built from teardown/pistonlab-3d with the
teardown skill, so these check what ships rather than run a browser: that it is
served, small enough for link previews, offered from the console, and that every
gallery engine solves to a layout the 3D view can draw at its published capacity.
"""

from __future__ import annotations

import asyncio
import json
import math
import types
from pathlib import Path

import pytest

from app.main import cache_control, piston_3d
from app.schemas_piston import PistonSimulateInput, run_piston_simulation

_ROOT = Path(__file__).resolve().parent.parent
_PAGE = _ROOT / "app" / "static" / "piston" / "3d" / "index.html"
_SRC = _ROOT / "teardown" / "pistonlab-3d"
_GALLERY = json.loads((_SRC / "gallery.json").read_text(encoding="utf-8"))
_DRAWN = {"single", "inline", "vee", "flat"}


def test_the_route_serves_the_built_page() -> None:
    response = piston_3d()
    assert Path(response.path) == _PAGE
    assert "<title>PistonLab 3D" in _PAGE.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ["/piston/3d", "/piston/3d/"])
def test_the_page_is_never_cached_stale(path: str) -> None:
    request = types.SimpleNamespace(url=types.SimpleNamespace(path=path, query=""))
    response = types.SimpleNamespace(headers={})

    async def call_next(_req):  # noqa: ANN001 - test stub
        return response

    assert asyncio.run(cache_control(request, call_next)).headers["Cache-Control"] == "no-cache, must-revalidate"


def test_the_built_page_is_self_contained_and_small() -> None:
    html = _PAGE.read_text(encoding="utf-8")
    # Link crawlers give up on big pages; three.js is inlined, so this is the budget.
    assert len(html.encode("utf-8")) < 1_000_000
    assert "<script src=" not in html
    assert "/piston/simulate" in html


def test_the_console_offers_the_3d_view() -> None:
    piston = _ROOT / "app" / "static" / "piston"
    assert 'id="open3d"' in (piston / "index.html").read_text(encoding="utf-8")
    js = (piston / "piston.js").read_text(encoding="utf-8")
    assert "function open3d" in js and "/piston/3d/#e=" in js


@pytest.mark.parametrize("engine", _GALLERY, ids=[g["id"] for g in _GALLERY])
def test_every_gallery_engine_solves_at_its_published_capacity(engine: dict) -> None:
    body = engine["body"]
    assert body["layout"]["kind"] in _DRAWN
    out = run_piston_simulation(PistonSimulateInput(**body, include_trace=True))
    cc = out.total_displacement_m3 * 1e6
    assert math.isclose(cc, engine["published_capacity_cc"], rel_tol=0.005)
    # The page draws from the layout's cylinder map and firing order.
    assert out.layout is not None
    assert len(out.layout.cylinder_map) == body["cylinders"]
    assert sorted(out.layout.firing_order) == list(range(1, body["cylinders"] + 1))
    assert out.trace and out.trace[0].theta_deg == -180 and out.trace[-1].theta_deg == 180


@pytest.mark.parametrize("engine", _GALLERY, ids=[g["id"] for g in _GALLERY])
def test_gallery_hardware_is_drawable(engine: dict) -> None:
    # The 3D view draws valvetrain, oil system and balance shafts from this data; the
    # solver never sees it, so it must at least agree with the valve counts it does see.
    hw = engine["hardware"]
    assert hw["valvetrain"] in {"dohc", "sohc", "ohv"}
    assert hw["oil"] in {"wet", "dry"}
    assert hw["balance_shafts"] in {0, 1, 2}
    vg = engine["body"].get("valve_geometry", {})
    valves = vg.get("intake_valves_per_cylinder", 2) + vg.get("exhaust_valves_per_cylinder", 2)
    if hw["valvetrain"] in {"sohc", "ohv"}:
        # one cam over a line of valves, or a block cam with rockers: two valves per cylinder
        assert valves == 2

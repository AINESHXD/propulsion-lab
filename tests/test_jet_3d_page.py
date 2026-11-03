"""The JetLab 3D page and the contract it relies on.

The page is a single HTML file built from teardown/jetlab-3d with the teardown
skill, so these check what ships rather than run a browser: that it is served,
small enough for link previews, and that every gallery engine solves through the
same endpoint the page calls, with the stations and hardware the 3D layout reads.
"""

from __future__ import annotations

import asyncio
import json
import types
from pathlib import Path

import pytest

from app.main import cache_control, jet_3d, simulate_ramjet, simulate_scramjet, simulate_turbofan, simulate_turbojet, simulate_turboprop
from app.schemas import RamjetInput, ScramjetInput, TurbofanInput, TurbojetInput, TurbopropInput

_ROOT = Path(__file__).resolve().parent.parent
_PAGE = _ROOT / "app" / "static" / "jet" / "3d" / "index.html"
_SRC = _ROOT / "teardown" / "jetlab-3d"
_GALLERY = json.loads((_SRC / "gallery.json").read_text(encoding="utf-8"))
_SOLVE = {
    "turbofan": (simulate_turbofan, TurbofanInput),
    "turbojet": (simulate_turbojet, TurbojetInput),
    "turboprop": (simulate_turboprop, TurbopropInput),
    "ramjet": (simulate_ramjet, RamjetInput),
    "scramjet": (simulate_scramjet, ScramjetInput),
}
# the stations the layout (kin.js) places geometry on, per family
_STATIONS = {
    "turbofan": {0, 2, 13, 3, 4, 45, 5, 9, 19},
    "turbojet": {0, 2, 3, 4, 5, 9},
    "turboprop": {0, 2, 3, 4, 45, 5, 9},
    "ramjet": {0, 2, 3, 4, 9},
    "scramjet": {0, 2, 3, 4, 9},
}


def test_the_route_serves_the_built_page() -> None:
    response = jet_3d()
    assert Path(response.path) == _PAGE
    assert "<title>JetLab 3D" in _PAGE.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ["/jet/3d", "/jet/3d/"])
def test_the_page_is_never_cached_stale(path: str) -> None:
    request = types.SimpleNamespace(url=types.SimpleNamespace(path=path, query=""))
    response = types.SimpleNamespace(headers={})

    async def call_next(_req):  # noqa: ANN001 - test stub
        return response

    assert asyncio.run(cache_control(request, call_next)).headers["Cache-Control"] == "no-cache, must-revalidate"


def test_the_built_page_is_self_contained_and_small() -> None:
    html = _PAGE.read_text(encoding="utf-8")
    assert len(html.encode("utf-8")) < 1_000_000
    assert "<script src=" not in html
    assert "/simulate/" in html


@pytest.mark.parametrize("engine", _GALLERY, ids=[g["id"] for g in _GALLERY])
def test_every_gallery_engine_solves_with_the_stations_the_layout_reads(engine: dict) -> None:
    solve, schema = _SOLVE[engine["family"]]
    out = solve(schema(**engine["body"]))
    assert out.thrust_N > 0
    assert _STATIONS[engine["family"]] <= {int(k) for k in out.station_table}
    for s in out.station_table.values():
        assert s.stagnation_temperature_K > 0 and s.stagnation_pressure_Pa > 0


@pytest.mark.parametrize("engine", _GALLERY, ids=[g["id"] for g in _GALLERY])
def test_gallery_hardware_is_drawable(engine: dict) -> None:
    hw = engine["hardware"]
    assert hw["diameter_m"] > 0
    family = engine["family"]
    if family in {"turbofan", "turbojet", "turboprop"}:
        assert hw["hpt"] >= 1 and hw["fuel_nozzles"] >= 1
        assert hw["spools"]["hp"] > 0
    if family == "turbofan":
        assert hw["fan_blades"] >= 10 and hw["hpc"] >= 1 and hw["lpt"] >= 1
        assert hw["spools"]["lp"] > 0
        assert hw["agb"] in {"fan", "core"}
        # a three-spool engine has the IP spool's compressor, turbine and speed together, or none of them
        assert ("ipc" in hw) == ("ipt" in hw) == ("ip" in hw["spools"])
        if "gear_ratio" in hw:
            # the drawn star gearbox (sun 32, ring 66) gives exactly this ratio
            assert abs(hw["gear_ratio"] - (1 + 66 / 32)) < 1e-9
    if family == "turboprop":
        assert hw["pt"] >= 1 and hw["spools"]["pt"] > 0

"""The custom engine builder's page and client contract.

The wizard ships as static JS, so these assert the contract the console depends
on rather than running the browser: that the overlay and its hooks exist, that
the step graph really branches instead of being a fixed list, and that every
solver key the wizard emits is one the API schema actually accepts.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.schemas_piston import (
    PistonLayoutIn,
    PistonSimulateInput,
    PistonValveGeometryIn,
    PistonValveTimingIn,
)

_ROOT = Path(__file__).resolve().parent.parent
_PISTON = _ROOT / "app" / "static" / "piston"

_HTML = (_PISTON / "index.html").read_text(encoding="utf-8")
_BUILDER = (_PISTON / "builder.js").read_text(encoding="utf-8")
_CONSOLE = (_PISTON / "piston.js").read_text(encoding="utf-8")
_CSS = (_PISTON / "piston.css").read_text(encoding="utf-8")


def test_the_builder_ships_with_the_console() -> None:
    assert (_PISTON / "builder.js").exists()
    # The console imports it and offers a way in.
    assert "builder.js" in _CONSOLE
    assert "openBuilder" in _CONSOLE and "initBuilder" in _CONSOLE
    assert 'id="openBuilder"' in _HTML


def test_the_overlay_and_its_controls_exist_on_the_page() -> None:
    for hook in ('id="builderOverlay"', 'id="bdBody"', 'id="bdProgress"',
                 'id="bdBack"', 'id="bdNext"', 'id="bdClose"'):
        assert hook in _HTML, hook
    # And the configuration card the built engine reports into.
    for hook in ('id="configCard"', 'id="configRows"', 'id="configVerdicts"'):
        assert hook in _HTML, hook
    assert ".bd-overlay" in _CSS and ".bd-choice" in _CSS


def test_the_flow_is_a_branching_graph_not_a_fixed_list() -> None:
    # Steps gate themselves on earlier answers; without `when` predicates this
    # would just be a linear form.
    gates = re.findall(r"^\s*when: \(a\) =>", _BUILDER, flags=re.MULTILINE)
    assert len(gates) >= 4, f"expected several conditional steps, found {len(gates)}"
    # The branches that matter: fuel only for spark, bank angle only for a V,
    # split pins only when odd-fire, crank plane only for a big V, boost only
    # when forced.
    assert 'a.ignition === "spark"' in _BUILDER
    assert 'a.layout_kind === "vee"' in _BUILDER
    assert "isEvenFire" in _BUILDER
    assert 'a.aspiration !== "naturally_aspirated"' in _BUILDER


def test_the_wizard_only_emits_keys_the_api_accepts() -> None:
    # Pull the payload keys out of specFromAnswers and check each is a real
    # field on the schema. A typo here would 422 at the worst possible moment.
    spec_block = _BUILDER.split("export function specFromAnswers")[1].split("\n}")[0]
    top_level = set(re.findall(r"^    (\w+):", spec_block, flags=re.MULTILINE))
    allowed = set(PistonSimulateInput.model_fields)
    assert top_level, "no payload keys found"
    assert top_level <= allowed, f"unknown keys: {sorted(top_level - allowed)}"


def test_the_nested_blocks_match_their_schemas() -> None:
    for marker, model in (
        ("layout: {", PistonLayoutIn),
        ("valve_timing: {", PistonValveTimingIn),
        ("valve_geometry: {", PistonValveGeometryIn),
    ):
        block = _BUILDER.split(marker)[1].split("},")[0]
        keys = set(re.findall(r"^      (\w+):", block, flags=re.MULTILINE))
        allowed = set(model.model_fields)
        assert keys, f"no keys parsed for {marker}"
        assert keys <= allowed, f"{marker} has unknown keys: {sorted(keys - allowed)}"


def test_the_console_sends_the_builder_extras_with_every_solve() -> None:
    # Layout, cam and head have no form controls, so they have to be merged into
    # the request body or a built engine silently reverts on the next slider drag.
    assert "builderExtras" in _CONSOLE
    assert "Object.assign(body, builderExtras)" in _CONSOLE
    # And a stock preset or family switch has to clear them.
    assert _CONSOLE.count("builderExtras = null") >= 2


def test_bore_and_stroke_come_back_from_the_server_not_a_js_copy() -> None:
    # The capacity solve is Python's job; the console writes back what the API
    # returned rather than recomputing the cube root itself.
    assert 'setKey("bore_m", mm(result.bore_m))' in _CONSOLE
    assert 'setKey("stroke_m", mm(result.stroke_m))' in _CONSOLE


def test_the_rpm_control_covers_the_range_the_builder_offers() -> None:
    # The wizard lets you build a 12000 rpm engine; the console slider must be
    # able to represent it instead of silently clamping.
    builder_max = int(re.search(r'key: "rpm", min: \d+, max: (\d+)', _BUILDER).group(1))
    console_max = int(re.search(r'data-key="rpm" min="\d+" max="(\d+)"', _HTML).group(1))
    assert console_max >= builder_max


def test_the_page_stays_honest_and_form_free() -> None:
    html = _HTML.lower()
    assert "<form" not in html
    for processor in ("stripe", "paypal", "checkout", "password"):
        assert processor not in html

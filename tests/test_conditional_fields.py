"""Console UI: fields that do not apply are hidden, not left to be guessed at.

A reviewer testing PropulsionLab pointed out that mixer inputs stayed on screen
in separate-flow mode and afterburner sliders stayed on screen with no
afterburner. An input that cannot affect the answer reads as "you forgot to fill
this in", so these assert the gating exists and stays wired.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_STATIC = _ROOT / "app" / "static"
_HTML = (_STATIC / "index.html").read_text(encoding="utf-8")
_JS = (_STATIC / "app.js").read_text(encoding="utf-8")
_CSS = (_STATIC / "styles.css").read_text(encoding="utf-8")


def test_the_advanced_form_has_a_visibility_mechanism() -> None:
    assert "applyAdvancedFieldVisibility" in _JS
    assert "readAdvancedFormValues" in _JS
    # It must re-evaluate on change, or it only works on first render.
    assert 'advancedInputGrid.addEventListener("change", applyAdvancedFieldVisibility)' in _JS


def test_configuration_only_fields_are_gated() -> None:
    # Each of these is meaningless outside one configuration and must declare it.
    for field, predicate in (
        ("mixer_pressure_loss_fraction", 'nozzle_configuration === "mixed"'),
        ("afterburner_exit_temperature_K", "use_afterburner"),
        ("afterburner_efficiency", "use_afterburner"),
        ("afterburner_pressure_loss_fraction", "use_afterburner"),
        ("third_stream_ratio", "third_stream"),
        ("third_stream_pressure_ratio", "third_stream"),
        ("variable_cycle_mode", "third_stream"),
    ):
        block = _JS.split(f'["{field}"')[1].split("],")[0]
        assert "showWhen" in block, f"{field} is not gated"
        assert predicate in block, f"{field} is gated on the wrong thing"


def test_the_mixer_field_no_longer_apologises_in_its_label() -> None:
    # It used to be labelled "(mixed only)" because it was always visible. Now
    # it is only visible when it applies, so the caveat is redundant.
    assert "Mixer ΔP/P (mixed only)" not in _JS


def test_the_afterburner_section_follows_the_variant() -> None:
    assert 'id="afterburnerSection"' in _HTML
    assert "applyVariantVisibility" in _JS
    assert 'variant !== "afterburning_turbojet"' in _JS


def test_the_preset_placeholder_does_not_read_as_empty() -> None:
    # A bare "Loading…" made a reviewer conclude the presets were never built.
    assert "<option value=\"\">Loading…</option>" not in _HTML
    assert "Loading presets" in _HTML


def test_efficiency_presets_are_named_points_not_a_fabricated_curve() -> None:
    # The UX idea was worth taking; interpolating along a "verified historical
    # curve" was not, because no such curve could be cited.
    assert 'id="efficiencyPreset"' in _HTML
    assert "EFFICIENCY_PRESETS" in _JS
    for name in ("legacy", "mature", "modern"):
        assert f"{name}:" in _JS
    # Values are written into the visible fields, so nothing is set unseen.
    assert "applyEfficiencyPreset" in _JS
    assert 'field.value = value' in _JS
    # And the page says plainly what they are not.
    assert "not a fitted historical curve" in _HTML


def test_the_hand_drawn_engine_icons_are_gone() -> None:
    assert 'class="ec-icon"' not in _HTML
    assert "ec-icon" not in _CSS


def test_the_engine_cards_still_carry_their_text() -> None:
    # Removing the icons must not have taken the labels with them.
    for cls in ("ec-code", "ec-name", "ec-desc"):
        assert _HTML.count(f'class="{cls}"') == 5, f"expected 5 {cls} spans"
    assert len(re.findall(r'data-engine="', _HTML)) >= 5

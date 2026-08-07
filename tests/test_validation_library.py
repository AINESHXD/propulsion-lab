"""The certified-engine validation library, and the rules that keep it honest.

The library's whole value is that PropulsionLab did not produce the numbers it
is judged against. These tests defend that: every case must carry a checkable
ICAO engine UID, the reference TSFC must be arithmetic on published figures,
and the assumption set must stay uniform across all engines. A model that only
agrees after per-engine tuning has demonstrated nothing.

The agreement bounds asserted here are deliberately loose and deliberately
*two-sided*. They exist to catch a regression in the solver or a corrupted data
file — not to certify the model as accurate. The measured disagreement is real
and is reported as-is.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.engine_core.validation import (
    ASSUMPTIONS,
    fan_pressure_ratio_for,
    load_cases,
    run_all,
    summarise,
)

_ROOT = Path(__file__).resolve().parent.parent
_DATA = _ROOT / "app" / "data" / "validation_cases.json"


# --------------------------------------------------------------------------- #
# the data must be checkable against its primary source
# --------------------------------------------------------------------------- #
def test_the_library_covers_a_real_spread_of_engines() -> None:
    cases = load_cases()["cases"]
    assert len(cases) >= 20, "the library is meant to be a library"
    bprs = [c["bypass_ratio"] for c in cases]
    oprs = [c["overall_pressure_ratio"] for c in cases]
    # Twenty variants of one engine would prove nothing about generality.
    assert min(bprs) < 1.0 and max(bprs) > 10.0, "bypass range is too narrow"
    assert min(oprs) < 15.0 and max(oprs) > 40.0, "pressure-ratio range is too narrow"
    assert len({c["manufacturer"] for c in cases}) >= 5


def test_every_case_can_be_traced_to_the_databank() -> None:
    for case in load_cases()["cases"]:
        assert case["icao_uid"], f"{case['name']} has no ICAO UID to check against"
        assert case["rated_thrust_N"] > 0
        assert case["fuel_flow_takeoff_kg_s"] > 0


def test_the_reference_is_arithmetic_on_published_numbers() -> None:
    # Reference TSFC must be fuel flow over thrust and nothing else — if it
    # were ever hand-edited toward the solver, the library would be worthless.
    for case in load_cases()["cases"]:
        expected = case["fuel_flow_takeoff_kg_s"] / case["rated_thrust_N"]
        assert case["reference_tsfc_kg_per_N_s"] == pytest.approx(expected, rel=1e-12)


def test_the_file_names_its_sources_and_its_limits() -> None:
    doc = json.loads(_DATA.read_text(encoding="utf-8"))
    assert "ICAO" in doc["primary_source"]
    note = doc["source_note"]
    assert "not tuned" in note
    assert "never fitted per engine" in note


def test_the_references_are_physically_sane() -> None:
    # Sea-level-static TSFC for a turbofan lives in roughly 0.2-0.7 lb/(lbf h).
    # Anything outside that is a units error, which is the failure mode most
    # likely to go unnoticed and most likely to embarrass.
    to_lb = 3600 * 2.20462 / 0.224809
    for case in load_cases()["cases"]:
        tsfc = case["reference_tsfc_kg_per_N_s"] * to_lb
        assert 0.20 < tsfc < 0.75, f"{case['name']}: TSFC {tsfc:.3f} lb/lbf/h is not credible"


# --------------------------------------------------------------------------- #
# the rules that make this validation rather than curve-fitting
# --------------------------------------------------------------------------- #
def test_the_assumption_set_is_uniform_and_not_per_engine() -> None:
    # Every unpublished quantity is a single scalar shared by all engines.
    for key, value in ASSUMPTIONS.items():
        assert isinstance(value, (int, float)), f"{key} varies per engine"


def test_the_fan_split_depends_only_on_published_bypass_ratio() -> None:
    # Fan pressure ratio has to fall as bypass ratio rises, or the jet
    # velocities cannot stay matched.
    ratios = [fan_pressure_ratio_for(b) for b in (0.6, 2.0, 5.0, 8.0, 11.6)]
    assert ratios == sorted(ratios, reverse=True), "fan split is not monotonic"
    assert 2.0 < ratios[0] < 3.2      # low bypass
    assert 1.4 < ratios[2] < 1.8      # CFM56 class
    assert 1.2 < ratios[-1] < 1.5     # geared turbofan


# --------------------------------------------------------------------------- #
# the measured result
# --------------------------------------------------------------------------- #
def test_every_engine_solves_at_the_shared_assumption_set() -> None:
    # Three of these did not converge at 1500 K: a bypass-11 fan cannot be
    # driven by a turbine that cold. Whatever assumption set ships must close
    # the power balance for the whole library, or the coverage is a fiction.
    results = run_all()
    assert len(results) == len(load_cases()["cases"])


def test_the_solver_ranks_the_engines_the_way_the_databank_does() -> None:
    # This is the claim PropulsionLab actually makes: trend-correct. It is a
    # far stronger test of the physics than absolute agreement, and it is what
    # survives the unpublished efficiencies.
    stats = summarise(run_all())
    assert stats["rank_correlation"] > 0.80, (
        "the solver no longer orders real engines the way certification data does"
    )


def test_the_known_bias_has_not_silently_moved() -> None:
    # The model runs systematically pessimistic under one uniform assumption
    # set. That is reported, not hidden. This bound is a regression guard: if
    # the bias drifts far from where it was measured, something changed in the
    # solver and the published figure needs revisiting.
    stats = summarise(run_all())
    assert 5.0 < stats["mean_absolute_error_percent"] < 40.0

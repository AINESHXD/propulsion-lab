"""Tests for the convergent-divergent (CD) nozzle option.

A divergent area ratio > 1 on a choked nozzle should produce a supersonic
exit Mach set by the isentropic area-Mach relation, with higher exit velocity
than the convergent (M=1) case. Area ratio = 1 must reproduce the convergent
nozzle exactly.
"""

from __future__ import annotations

import pytest

from app.engine_core.gas_properties import (
    area_ratio_from_mach,
    supersonic_mach_from_area_ratio,
)
from app.engine_core.ramjet import RamjetCycleInputs, simulate_ramjet_cycle
from app.engine_core.scramjet import ScramjetCycleInputs, simulate_scramjet_cycle


# ---------------------------------------------------------------------------
# Area-Mach relation
# ---------------------------------------------------------------------------


def test_area_ratio_round_trip_supersonic() -> None:
    """supersonic_mach_from_area_ratio inverts area_ratio_from_mach."""

    for mach in (1.5, 2.0, 3.0, 5.0):
        ar = area_ratio_from_mach(mach, gamma=1.33)
        recovered = supersonic_mach_from_area_ratio(ar, gamma=1.33)
        assert recovered == pytest.approx(mach, rel=1e-3)


def test_area_ratio_unity_is_sonic() -> None:
    assert supersonic_mach_from_area_ratio(1.0) == 1.0
    assert area_ratio_from_mach(1.0, gamma=1.4) == pytest.approx(1.0, rel=1e-9)


def test_area_ratio_matches_textbook_air() -> None:
    """A/A* ≈ 1.688 at M=2 for γ=1.4 (standard isentropic table value)."""

    assert area_ratio_from_mach(2.0, gamma=1.4) == pytest.approx(1.6875, rel=2e-3)


# ---------------------------------------------------------------------------
# CD nozzle in the ramjet / scramjet solvers
# ---------------------------------------------------------------------------


def test_ramjet_cd_nozzle_exits_supersonic_and_faster() -> None:
    conv = simulate_ramjet_cycle(RamjetCycleInputs(mach=2.5))
    cd = simulate_ramjet_cycle(
        RamjetCycleInputs(mach=2.5, nozzle_divergent_area_ratio=4.0)
    )
    # Convergent nozzle is capped at M=1; CD nozzle must exceed it.
    assert conv["station_table"][9]["mach"] == pytest.approx(1.0, abs=1e-6)
    assert cd["station_table"][9]["mach"] > 1.5
    # Faster exhaust -> higher exit velocity.
    assert cd["exit_velocity_m_s"] > conv["exit_velocity_m_s"]


def test_ramjet_area_ratio_one_reproduces_convergent() -> None:
    conv = simulate_ramjet_cycle(RamjetCycleInputs(mach=2.5))
    explicit = simulate_ramjet_cycle(
        RamjetCycleInputs(mach=2.5, nozzle_divergent_area_ratio=1.0)
    )
    assert conv["thrust_N"] == pytest.approx(explicit["thrust_N"], rel=1e-12)
    assert conv["exit_velocity_m_s"] == pytest.approx(
        explicit["exit_velocity_m_s"], rel=1e-12
    )


def test_scramjet_cd_nozzle_lifts_exit_mach() -> None:
    """The scramjet defaults to a CD nozzle; forcing a convergent (AR=1) nozzle
    caps the exit at M=1 and the default CD nozzle must beat it."""

    conv = simulate_scramjet_cycle(
        ScramjetCycleInputs(mach=6.0, nozzle_divergent_area_ratio=1.0)
    )
    cd = simulate_scramjet_cycle(ScramjetCycleInputs(mach=6.0))  # default AR=6
    assert conv["station_table"][9]["mach"] == pytest.approx(1.0, abs=1e-6)
    assert cd["station_table"][9]["mach"] > conv["station_table"][9]["mach"]
    assert cd["station_table"][9]["mach"] > 1.5
    assert cd["thrust_N"] > 0.0


def test_cd_nozzle_note_advertises_supersonic_exit() -> None:
    cd = simulate_ramjet_cycle(
        RamjetCycleInputs(mach=3.0, nozzle_divergent_area_ratio=5.0)
    )
    notes = cd["station_table"][9].get("notes") or []
    assert any("supersonic" in n.lower() for n in notes)


# ---------------------------------------------------------------------------
# Day 7 — normal shock in the divergent section (heavily over-expanded CD nozzle)
# ---------------------------------------------------------------------------

from app.engine_core.constants import R_air, cp_gas, gamma_gas
from app.engine_core.gas_properties import normal_shock_pressure_ratio
from app.engine_core.streams import expand_nozzle_stream
from app.engine_core.types import StationState


def test_normal_shock_pressure_ratio_textbook() -> None:
    # P2/P1 across a normal shock at M=2, gamma=1.4 -> 4.5 (standard table).
    assert normal_shock_pressure_ratio(2.0, gamma=1.4) == pytest.approx(4.5, rel=1e-6)
    assert normal_shock_pressure_ratio(1.0) == 1.0  # no shock at M=1


def _hot_inlet(pt_pa: float) -> StationState:
    return StationState(
        station=4, name="combustor exit",
        stagnation_temperature_K=2000.0, stagnation_pressure_Pa=pt_pa,
    )


def _expand(area_ratio: float, ambient_pa: float = 101325.0, pt_pa: float = 300000.0):
    return expand_nozzle_stream(
        _hot_inlet(pt_pa), ambient_pa, 20.0, 0.03, 0.0, 0.95, 9,
        "test nozzle", gamma_gas, cp_gas, R_air, True,
        divergent_area_ratio=area_ratio,
    )


def test_cd_nozzle_clean_supersonic_below_shock_threshold() -> None:
    """A modest area ratio flows full supersonic with no internal shock."""

    r = _expand(area_ratio=3.0)
    assert r.metadata["shock_in_nozzle"] is False
    assert r.exit_mach > 1.5


def test_cd_nozzle_internal_shock_gives_subsonic_exit() -> None:
    """Past the shock-at-exit threshold a normal shock stands in the divergent
    section: the exit drops subsonic and is flagged."""

    r = _expand(area_ratio=4.0)
    assert r.metadata["shock_in_nozzle"] is True
    assert r.exit_mach < 1.0
    assert r.exit_velocity_m_s > 0.0
    assert "shock" in r.metadata["expansion_status"].lower()
    assert any("shock" in n.lower() for n in (r.state.notes or []))


def test_ramjet_matched_area_ratio_has_no_shock() -> None:
    """A modest area ratio stays full-flowing supersonic in the full cycle."""

    out = simulate_ramjet_cycle(
        RamjetCycleInputs(mach=3.5, altitude_m=18000.0, nozzle_divergent_area_ratio=3.0)
    )
    assert out["station_table"][9]["mach"] > 1.0
    assert not any("shock in" in w.lower() for w in out["warnings"])

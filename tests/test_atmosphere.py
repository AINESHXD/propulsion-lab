"""Tests for the ISA atmosphere model."""

import pytest

from app.engine_core.atmosphere import isa_atmosphere


def test_atmosphere_sea_level_matches_isa_reference() -> None:
    """Sea-level ISA values should match standard reference values closely."""

    atmosphere = isa_atmosphere(0.0)

    assert atmosphere.temperature_K == pytest.approx(288.15, rel=1e-4)
    assert atmosphere.pressure_Pa == pytest.approx(101325.0, rel=1e-4)
    assert atmosphere.density_kg_m3 == pytest.approx(1.225, rel=1e-3)


def test_atmosphere_at_11_km_matches_tropopause_reference() -> None:
    """At 11 km, ISA should be near 216.65 K and 22.6 kPa."""

    atmosphere = isa_atmosphere(11000.0)

    assert atmosphere.temperature_K == pytest.approx(216.65, rel=1e-4)
    assert atmosphere.pressure_Pa == pytest.approx(22600.0, rel=0.02)

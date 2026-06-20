"""PistonLab reciprocating-engine cycle solver (Python source of truth).

This package is the credible-engine core that the client-side console mirrors.
It moves PistonLab past the closed-form air-standard formula
(``eta = 1 - 1/r**(gamma-1)``) to a *crank-angle-resolved* first-law cycle:

* :mod:`geometry`  — slider-crank cylinder volume ``V(theta)``.
* :mod:`wiebe`     — finite heat-release burn fraction ``x_b(theta)``.
* :mod:`cycle`     — march ``dU = dQ - p dV`` over the closed cycle and report
                     indicated work, IMEP, power, torque and thermal efficiency.

Everything is reduced-order and educational; indicated numbers here are not
brake numbers (friction/pumping arrive in later modules).
"""

from app.engine_core.piston.geometry import (
    CylinderGeometry,
    clearance_volume,
    cylinder_volume,
    displacement_volume,
)
from app.engine_core.piston.wiebe import wiebe_burn_fraction, wiebe_burn_rate
from app.engine_core.piston.friction import chen_flynn_fmep_Pa
from app.engine_core.piston.aspiration import ASPIRATION_MODES, supercharger_power_W
from app.engine_core.piston.fuel import (
    FUEL_NAMES,
    FUELS,
    Fuel,
    fuel_air_ratio,
    get_fuel,
    lambda_from_phi,
    specific_heat_release_J_per_kg_charge,
    stoichiometric_afr,
)
from app.engine_core.piston.cycle import (
    PistonCycleInputs,
    PistonCycleResult,
    simulate_piston_cycle,
)

__all__ = [
    "CylinderGeometry",
    "clearance_volume",
    "cylinder_volume",
    "displacement_volume",
    "wiebe_burn_fraction",
    "wiebe_burn_rate",
    "chen_flynn_fmep_Pa",
    "ASPIRATION_MODES",
    "supercharger_power_W",
    "Fuel",
    "FUELS",
    "FUEL_NAMES",
    "get_fuel",
    "stoichiometric_afr",
    "fuel_air_ratio",
    "lambda_from_phi",
    "specific_heat_release_J_per_kg_charge",
    "PistonCycleInputs",
    "PistonCycleResult",
    "simulate_piston_cycle",
]

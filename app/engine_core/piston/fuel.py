"""Fuel thermochemistry for PistonLab (Day 7).

Up to now the cycle solver took a raw ``heat_release_J_per_kg`` of charge as a
direct input. That is a knob, not physics. This module replaces it with real
fuelling: pick a fuel, pick how rich or lean the mixture is, and the heat
release follows from the fuel's chemistry.

The chain is:

    stoichiometric AFR  <- fuel C/H/O composition (mass balance of combustion)
    fuel-air ratio  f   =  phi / AFR_stoich            (phi = equivalence ratio)
    heat per kg charge  =  f * LHV * eta_combustion

with the air-excess ratio ``lambda = 1 / phi`` reported alongside (lambda = 1 is
stoichiometric, lambda > 1 lean, lambda < 1 rich).

Stoichiometric AFR is derived from the combustion mass balance, not hard-coded:
for a fuel ``C_c H_h O_o`` burning to CO2 + H2O the oxygen demand is
``c + h/4 - o/2`` moles of O2 per mole of fuel, and air carries 3.762 moles of
N2 per mole of O2. That gives gasoline ~14.7 and diesel ~14.5, the textbook
numbers, as a *consequence* of the chemistry rather than an assumption.
"""

from __future__ import annotations

from dataclasses import dataclass

# Atomic / molecular masses (g/mol). AFR is a mass ratio, so the gram units
# cancel; only internal consistency matters.
_M_C = 12.011
_M_H = 1.008
_M_O = 15.999
_M_O2 = 31.998
_M_N2 = 28.013

# Dry air composition: 20.95 % O2 / 78.09 % N2 by mole -> 3.762 mol N2 per mol O2.
_N2_PER_O2 = 3.762
# Mass of air that supplies exactly one mole of O2 (the oxidiser book-keeping
# unit): one O2 plus its escorting nitrogen.
_AIR_MASS_PER_MOL_O2 = _M_O2 + _N2_PER_O2 * _M_N2   # ~= 137.39 g


@dataclass(frozen=True, slots=True)
class Fuel:
    """A liquid fuel as a single representative surrogate molecule C_c H_h O_o.

    Real gasoline and diesel are blends; a surrogate with the right carbon and
    hydrogen content reproduces the stoichiometric air-fuel ratio and is the
    standard reduced-order treatment.
    """

    name: str
    carbon: float                      # C atoms per surrogate molecule
    hydrogen: float                    # H atoms
    oxygen: float                      # O atoms (alcohols carry their own O)
    lower_heating_value_J_per_kg: float
    density_kg_per_m3: float
    # Knock / ignition character (used by the operating-limits module). RON is
    # None for a compression-ignition fuel (diesel), where the limit is smoke,
    # not spark knock. ``ignition`` is the conventional engine pairing.
    research_octane_number: float | None = None
    ignition: str = "spark"            # "spark" (SI) | "compression" (CI)

    @property
    def molar_mass_g_per_mol(self) -> float:
        return self.carbon * _M_C + self.hydrogen * _M_H + self.oxygen * _M_O

    @property
    def oxygen_demand_mol(self) -> float:
        """Moles of O2 to fully burn one mole of fuel to CO2 + H2O."""

        return self.carbon + self.hydrogen / 4.0 - self.oxygen / 2.0

    @property
    def stoichiometric_afr(self) -> float:
        """Stoichiometric air-fuel ratio (mass of air per mass of fuel)."""

        air_mass = self.oxygen_demand_mol * _AIR_MASS_PER_MOL_O2
        return air_mass / self.molar_mass_g_per_mol


# Educational fuel set. Surrogate formulae chosen so the derived stoichiometric
# AFR lands on the well-known value; LHV and density are public reference data.
FUELS: dict[str, Fuel] = {
    # C8H16 -> AFR ~= 14.7; pump-grade RON ~95, spark ignition.
    "gasoline": Fuel("Gasoline", 8.0, 16.0, 0.0, 43.5e6, 745.0, 95.0, "spark"),
    # C13H24 -> AFR ~= 14.5; compression ignition, no RON (smoke-limited).
    "diesel": Fuel("Diesel", 13.0, 24.0, 0.0, 42.8e6, 832.0, None, "compression"),
    # C2H6O  -> AFR ~= 9.0; very knock-resistant (RON ~108).
    "ethanol": Fuel("Ethanol", 2.0, 6.0, 1.0, 26.8e6, 789.0, 108.0, "spark"),
    # CH4O   -> AFR ~= 6.4; RON ~109.
    "methanol": Fuel("Methanol", 1.0, 4.0, 1.0, 19.9e6, 792.0, 109.0, "spark"),
}

FUEL_NAMES = tuple(FUELS.keys())


def get_fuel(name: str) -> Fuel:
    """Look up a fuel by case-insensitive key, raising ValueError if unknown."""

    try:
        return FUELS[name.strip().casefold()]
    except (KeyError, AttributeError) as exc:
        raise ValueError(
            f"Unknown fuel {name!r}; choose one of {FUEL_NAMES}."
        ) from exc


def stoichiometric_afr(name: str) -> float:
    """Stoichiometric air-fuel ratio for a named fuel."""

    return get_fuel(name).stoichiometric_afr


def lambda_from_phi(equivalence_ratio: float) -> float:
    """Air-excess ratio lambda = 1 / phi (lambda > 1 is lean)."""

    if equivalence_ratio <= 0.0:
        raise ValueError("equivalence_ratio (phi) must be positive.")
    return 1.0 / equivalence_ratio


def fuel_air_ratio(name: str, equivalence_ratio: float) -> float:
    """Actual fuel-air mass ratio f = phi / AFR_stoich for a named fuel.

    phi = 1 gives the stoichiometric f = 1 / AFR_stoich; richer (phi > 1) adds
    more fuel per unit air, leaner (phi < 1) less.
    """

    if equivalence_ratio <= 0.0:
        raise ValueError("equivalence_ratio (phi) must be positive.")
    return equivalence_ratio / get_fuel(name).stoichiometric_afr


def specific_heat_release_J_per_kg_charge(
    name: str,
    equivalence_ratio: float,
    combustion_efficiency: float = 1.0,
) -> float:
    """Heat released per kilogram of (air) charge for a named fuel.

    ``q = f * LHV * eta_combustion`` with ``f`` the fuel-air ratio. This is the
    quantity that replaces the old raw ``heat_release_J_per_kg`` input: it is the
    chemical energy actually liberated into the trapped charge.
    """

    if not 0.0 < combustion_efficiency <= 1.0:
        raise ValueError("combustion_efficiency must be in (0, 1].")
    fuel = get_fuel(name)
    f = fuel_air_ratio(name, equivalence_ratio)
    return f * fuel.lower_heating_value_J_per_kg * combustion_efficiency

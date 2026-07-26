"""Aspiration: naturally aspirated, turbocharged, supercharged.

Boost raises the manifold (intake) pressure, which packs a denser charge into
the cylinder, so more fuel can be burned and both IMEP and power rise. The
crucial difference between the two ways of making boost is *who pays for it*:

* **Supercharger** — the compressor is belt-driven straight off the crankshaft,
  so its compression work is a **parasitic load that comes straight out of
  brake power**.
* **Turbocharger** — the compressor is driven by a turbine in the exhaust, so it
  costs the crankshaft nothing directly. It is *not* free: the turbine can only
  extract work by expanding the exhaust across itself, and that raises the
  pressure the piston has to push against on the exhaust stroke.

Turbocharger back-pressure
--------------------------
The turbine's cost is found from the shaft power balance rather than assumed.
On a common shaft the turbine must supply the compressor::

    eta_mech * W_turbine = W_compressor

with the turbine's work per unit mass following the isentropic expansion::

    W_turbine = m_exh * cp_exh * T_exh * (1 - PR_t ** -kappa_e) * eta_t

Solving that for the expansion ratio the turbine needs::

    X    = W_compressor / (eta_mech * m_exh * cp_exh * T_exh * eta_t)
    PR_t = (1 - X) ** (-1 / kappa_e)

and the exhaust manifold then sits at ``PR_t`` times whatever pressure is
downstream of the turbine. Everything on the right-hand side is already known
at the end of a cycle solve, so no new fitted parameter is introduced beyond the
turbine's isentropic and mechanical efficiencies.

``X >= 1`` means the exhaust stream simply does not carry enough enthalpy to
drive the compressor to that boost: the turbo would not spool to it. That case
is reported rather than silently clamped.
"""

from __future__ import annotations

ASPIRATION_MODES = ("naturally_aspirated", "turbocharged", "supercharged")

_GAMMA_AIR = 1.4          # fresh air being compressed (not burned charge)

# Burned-gas properties through the turbine. Constant values, consistent with
# the constant-specific-heat assumption the cycle integrator makes.
_GAMMA_EXHAUST = 1.33
_CP_EXHAUST_J_PER_KG_K = 1150.0

# Above this the turbine is asking for essentially all of the exhaust enthalpy
# and the expansion ratio runs away. Past it the boost is treated as
# unsustainable and the result is flagged.
_MAX_ENTHALPY_FRACTION = 0.92


def compressor_power_W(
    air_mass_flow_kg_s: float,
    inlet_temperature_K: float,
    pressure_ratio: float,
    efficiency: float,
    gas_constant_J_per_kg_K: float = 287.0,
) -> float:
    """Shaft power [W] to compress air to ``pressure_ratio``.

    Isentropic compression work per unit mass, derated by isentropic
    efficiency, times the mass flow. Returns 0 when there is no boost.

    The inlet temperature passed here is the manifold temperature, which is
    measured *after* any intercooler. Using it as the compressor inlet slightly
    overstates the work, and it is applied identically to both the belt-driven
    and the exhaust-driven compressor so the two stay comparable.
    """

    if efficiency <= 0.0 or efficiency > 1.0:
        raise ValueError("Compressor efficiency must be in (0, 1].")
    if pressure_ratio <= 1.0 or air_mass_flow_kg_s <= 0.0:
        return 0.0

    cp = _GAMMA_AIR * gas_constant_J_per_kg_K / (_GAMMA_AIR - 1.0)
    ideal_work_per_kg = cp * inlet_temperature_K * (
        pressure_ratio ** ((_GAMMA_AIR - 1.0) / _GAMMA_AIR) - 1.0
    )
    return air_mass_flow_kg_s * ideal_work_per_kg / efficiency


def supercharger_power_W(
    air_mass_flow_kg_s: float,
    inlet_temperature_K: float,
    pressure_ratio: float,
    efficiency: float,
    gas_constant_J_per_kg_K: float = 287.0,
) -> float:
    """Parasitic crank power [W] to drive a belt-driven supercharger.

    Identical compression work to :func:`compressor_power_W`; the distinction is
    where it is paid from. A supercharger's comes off the crankshaft, so this
    figure is debited from brake power.
    """

    return compressor_power_W(
        air_mass_flow_kg_s=air_mass_flow_kg_s,
        inlet_temperature_K=inlet_temperature_K,
        pressure_ratio=pressure_ratio,
        efficiency=efficiency,
        gas_constant_J_per_kg_K=gas_constant_J_per_kg_K,
    )


def turbine_expansion_ratio(
    compressor_power_W_: float,
    exhaust_mass_flow_kg_s: float,
    exhaust_temperature_K: float,
    turbine_efficiency: float = 0.70,
    mechanical_efficiency: float = 0.98,
) -> tuple[float, bool]:
    """Expansion ratio the turbine needs to drive its compressor.

    Returns ``(pressure_ratio, sustainable)``. ``sustainable`` is False when the
    exhaust stream cannot carry the required enthalpy, in which case the ratio
    is clamped at the limit rather than diverging.
    """

    if not 0.0 < turbine_efficiency <= 1.0:
        raise ValueError("Turbine efficiency must be in (0, 1].")
    if not 0.0 < mechanical_efficiency <= 1.0:
        raise ValueError("Turbo mechanical efficiency must be in (0, 1].")
    if compressor_power_W_ <= 0.0:
        return 1.0, True
    if exhaust_mass_flow_kg_s <= 0.0 or exhaust_temperature_K <= 0.0:
        raise ValueError("Exhaust mass flow and temperature must be positive.")

    available = (
        mechanical_efficiency * exhaust_mass_flow_kg_s
        * _CP_EXHAUST_J_PER_KG_K * exhaust_temperature_K * turbine_efficiency
    )
    fraction = compressor_power_W_ / available
    sustainable = fraction < _MAX_ENTHALPY_FRACTION
    fraction = min(fraction, _MAX_ENTHALPY_FRACTION)

    kappa = (_GAMMA_EXHAUST - 1.0) / _GAMMA_EXHAUST
    return (1.0 - fraction) ** (-1.0 / kappa), sustainable


def turbine_back_pressure_Pa(
    compressor_power_W_: float,
    exhaust_mass_flow_kg_s: float,
    exhaust_temperature_K: float,
    downstream_pressure_Pa: float,
    turbine_efficiency: float = 0.70,
    mechanical_efficiency: float = 0.98,
) -> tuple[float, float, bool]:
    """Exhaust manifold pressure a turbo has to run to make its boost.

    Returns ``(manifold_pressure_Pa, expansion_ratio, sustainable)``. The
    manifold sits at the turbine's expansion ratio above whatever is downstream
    of it, so pipe restriction and turbine back-pressure compose in the physical
    order: restriction first, then the turbine on top.
    """

    if downstream_pressure_Pa <= 0.0:
        raise ValueError("downstream_pressure_Pa must be positive.")

    ratio, sustainable = turbine_expansion_ratio(
        compressor_power_W_=compressor_power_W_,
        exhaust_mass_flow_kg_s=exhaust_mass_flow_kg_s,
        exhaust_temperature_K=exhaust_temperature_K,
        turbine_efficiency=turbine_efficiency,
        mechanical_efficiency=mechanical_efficiency,
    )
    return downstream_pressure_Pa * ratio, ratio, sustainable

"""Crank-angle first-law cycle integrator.

This is the engine that makes PistonLab credible. Instead of the closed-form
air-standard formula, it marches the first law of thermodynamics for the
in-cylinder gas, crank-angle step by crank-angle step, over the closed part of
the cycle (intake-valve-close -> exhaust-valve-open, i.e. compression +
combustion + expansion)::

    dU = dQ_combustion - p dV          (single zone, valves closed)

with the cylinder volume ``V(theta)`` from the true slider-crank kinematics and
the heat release ``dQ`` from the Wiebe burn law. Internal energy and pressure
close from the ideal-gas relations ``U = m c_v T`` and ``p V = m R T``.

What this module reports are *indicated* quantities (work done on the piston by
the gas). Friction, pumping and the resulting *brake* numbers arrive in later
modules; nothing here is a brake or dyno figure.

Constant specific heats are used for now (variable c_p / dissociation are a
later upgrade, mirroring PropulsionLab's real-gas path).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.engine_core.piston.aspiration import ASPIRATION_MODES, supercharger_power_W
from app.engine_core.piston.friction import chen_flynn_fmep_Pa
from app.engine_core.piston.fuel import (
    fuel_air_ratio,
    get_fuel,
    lambda_from_phi,
    specific_heat_release_J_per_kg_charge,
)
from app.engine_core.piston.geometry import CylinderGeometry, cylinder_volume
from app.engine_core.piston.limits import evaluate_operating_limits
from app.engine_core.piston.heat_transfer import (
    wall_surface_area_m2,
    woschni_coefficient,
    woschni_velocity,
)
from app.engine_core.piston.wiebe import wiebe_burn_fraction

_R_AIR = 287.0          # J/kg.K, dry air
_DEG = math.pi / 180.0


@dataclass(slots=True, frozen=True)
class PistonCycleInputs:
    """One operating point for the crank-angle cycle solver."""

    # Geometry
    bore_m: float = 0.086
    stroke_m: float = 0.086
    compression_ratio: float = 10.5
    rod_ratio: float = 3.5
    cylinders: int = 4
    strokes_per_cycle: int = 4               # 4-stroke (2 rev/cycle) or 2-stroke

    # Operating point
    rpm: float = 3000.0

    # Gas + initial (trapped) state at BDC / intake-valve-close
    gamma: float = 1.35                      # burned-charge-ish constant gamma
    gas_constant_J_per_kg_K: float = _R_AIR
    intake_temperature_K: float = 330.0
    intake_pressure_Pa: float = 1.0e5        # manifold pressure (throttle: < atm; boost: > atm)
    exhaust_pressure_Pa: float = 1.0e5       # exhaust back-pressure (>= intake when throttled)

    # Aspiration. The manifold pressure above is the boost; the mode decides who
    # pays for it — a supercharger debits crank power, a turbo (first cut) does not.
    aspiration: str = "naturally_aspirated"  # naturally_aspirated | turbocharged | supercharged
    ambient_pressure_Pa: float = 1.0e5       # reference ambient for boost + SC work
    supercharger_efficiency: float = 0.65

    # Heat release (per unit mass of trapped charge). Used directly only when no
    # fuel is selected (the legacy/raw path); when ``fuel`` is set, the heat
    # release is computed from fuel thermochemistry below and this is ignored.
    heat_release_J_per_kg: float = 2.5e6

    # Fuel thermochemistry (Day 7). Select a fuel and the heat release follows
    # from its chemistry and the mixture strength, instead of a raw kJ/kg:
    #   q_per_kg_charge = (phi / AFR_stoich) * LHV * combustion_efficiency.
    # fuel=None keeps the legacy raw-heat path (backward compatible).
    fuel: str | None = None                  # "gasoline" | "diesel" | "ethanol" | "methanol"
    equivalence_ratio: float = 1.0           # phi: 1 stoich, <1 lean, >1 rich
    combustion_efficiency: float = 0.98      # fraction of fuel energy released

    # Wiebe combustion
    combustion_start_deg: float = -15.0      # crank angle of spark/SOC (BTDC)
    burn_duration_deg: float = 50.0
    wiebe_a: float = 5.0
    wiebe_m: float = 2.0

    # Wall heat transfer (Woschni). Multiplier 0 = adiabatic (recovers the
    # closed air-standard limit); 1 = nominal Woschni loss.
    wall_temperature_K: float = 450.0
    wall_heat_transfer_multiplier: float = 1.0

    # Friction (Chen-Flynn FMEP) and fuel. The friction multiplier scales the
    # whole FMEP (0 = frictionless, brake == indicated); the LHV converts heat
    # release back to a fuel mass for BSFC.
    friction_multiplier: float = 1.0
    fuel_lhv_J_per_kg: float = 43.5e6        # gasoline lower heating value

    # Integration window (closed cycle: BDC -> BDC across TDC=0)
    theta_start_deg: float = -180.0
    theta_end_deg: float = 180.0
    d_theta_deg: float = 0.5

    def __post_init__(self) -> None:
        if self.bore_m <= 0 or self.stroke_m <= 0:
            raise ValueError("Bore and stroke must be positive.")
        if self.compression_ratio <= 1.0:
            raise ValueError("Compression ratio must exceed 1.")
        if self.rod_ratio <= 1.0:
            raise ValueError("Rod ratio (L/a) must exceed 1.")
        if self.strokes_per_cycle not in (2, 4):
            raise ValueError("strokes_per_cycle must be 2 or 4.")
        if self.cylinders < 1:
            raise ValueError("cylinders must be >= 1.")
        if self.rpm <= 0:
            raise ValueError("rpm must be positive.")
        if self.gamma <= 1.0:
            raise ValueError("gamma must exceed 1.")
        if self.heat_release_J_per_kg < 0.0:
            raise ValueError("heat_release_J_per_kg must be >= 0.")
        if self.d_theta_deg <= 0.0 or self.d_theta_deg > 5.0:
            raise ValueError("d_theta_deg must be in (0, 5].")
        if self.theta_end_deg <= self.theta_start_deg:
            raise ValueError("theta_end must be after theta_start.")
        if self.wall_heat_transfer_multiplier < 0.0:
            raise ValueError("wall_heat_transfer_multiplier must be >= 0.")
        if self.wall_temperature_K <= 0.0:
            raise ValueError("wall_temperature_K must be positive.")
        if self.friction_multiplier < 0.0:
            raise ValueError("friction_multiplier must be >= 0.")
        if self.fuel_lhv_J_per_kg <= 0.0:
            raise ValueError("fuel_lhv_J_per_kg must be positive.")
        if self.intake_pressure_Pa <= 0.0 or self.exhaust_pressure_Pa <= 0.0:
            raise ValueError("Intake and exhaust pressures must be positive.")
        if self.aspiration not in ASPIRATION_MODES:
            raise ValueError(f"aspiration must be one of {ASPIRATION_MODES}.")
        if self.ambient_pressure_Pa <= 0.0:
            raise ValueError("ambient_pressure_Pa must be positive.")
        if not 0.0 < self.supercharger_efficiency <= 1.0:
            raise ValueError("supercharger_efficiency must be in (0, 1].")
        if self.equivalence_ratio <= 0.0:
            raise ValueError("equivalence_ratio (phi) must be positive.")
        if not 0.0 < self.combustion_efficiency <= 1.0:
            raise ValueError("combustion_efficiency must be in (0, 1].")
        if self.fuel is not None:
            get_fuel(self.fuel)              # validates the name (raises ValueError)


@dataclass(slots=True, frozen=True)
class PistonCycleResult:
    """Indicated performance + the P-V/T trace for one operating point."""

    # Indicated (gas-on-piston) performance.
    indicated_work_J: float
    imep_Pa: float
    indicated_power_W: float
    indicated_torque_Nm: float
    thermal_efficiency: float
    air_standard_efficiency: float
    peak_pressure_Pa: float
    peak_temperature_K: float
    trapped_mass_kg: float
    heat_released_J: float
    wall_heat_loss_J: float                  # heat lost to the cylinder walls
    energy_residual_J: float                 # first-law closure check (~0)

    # Gas-exchange (pumping) loop and net indicated work.
    pmep_Pa: float                           # pumping MEP = p_exhaust - p_intake
    pumping_work_J: float                    # pumping loss per cylinder per cycle
    net_imep_Pa: float                       # gross IMEP - PMEP
    net_indicated_work_J: float

    # Brake (crankshaft) performance after pumping + friction. Below indicated.
    fmep_Pa: float
    bmep_Pa: float
    brake_work_J: float
    brake_power_W: float
    brake_torque_Nm: float
    mechanical_efficiency: float             # brake / indicated
    brake_thermal_efficiency: float
    bsfc_g_per_kWh: float                    # brake specific fuel consumption
    fuel_mass_per_cycle_kg: float

    # Aspiration.
    aspiration: str
    boost_pressure_Pa: float                 # manifold - ambient (gauge; <0 when throttled)
    supercharger_power_W: float              # parasitic crank power (0 for NA/turbo)

    # Fuelling (Day 7). "manual" fuel means the raw heat-per-kg path was used;
    # equivalence_ratio/lambda are then passthrough inputs, not chemistry.
    fuel: str                                # fuel key, or "manual"
    equivalence_ratio: float                 # phi
    lambda_air: float                        # 1 / phi
    fuel_air_ratio: float                    # actual fuel/air mass ratio
    air_fuel_ratio: float                    # actual air/fuel mass ratio

    # Operating-limit flags (knock / smoke / lean misfire). Empty when within
    # limits or when no fuel is selected. Each is {kind, severity, message}.
    operating_warnings: list[dict[str, str]] = field(default_factory=list)

    trace: list[dict[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicated_work_J": self.indicated_work_J,
            "imep_Pa": self.imep_Pa,
            "indicated_power_W": self.indicated_power_W,
            "indicated_torque_Nm": self.indicated_torque_Nm,
            "thermal_efficiency": self.thermal_efficiency,
            "air_standard_efficiency": self.air_standard_efficiency,
            "peak_pressure_Pa": self.peak_pressure_Pa,
            "peak_temperature_K": self.peak_temperature_K,
            "trapped_mass_kg": self.trapped_mass_kg,
            "heat_released_J": self.heat_released_J,
            "wall_heat_loss_J": self.wall_heat_loss_J,
            "energy_residual_J": self.energy_residual_J,
            "pmep_Pa": self.pmep_Pa,
            "pumping_work_J": self.pumping_work_J,
            "net_imep_Pa": self.net_imep_Pa,
            "net_indicated_work_J": self.net_indicated_work_J,
            "fmep_Pa": self.fmep_Pa,
            "bmep_Pa": self.bmep_Pa,
            "brake_work_J": self.brake_work_J,
            "brake_power_W": self.brake_power_W,
            "brake_torque_Nm": self.brake_torque_Nm,
            "mechanical_efficiency": self.mechanical_efficiency,
            "brake_thermal_efficiency": self.brake_thermal_efficiency,
            "bsfc_g_per_kWh": self.bsfc_g_per_kWh,
            "fuel_mass_per_cycle_kg": self.fuel_mass_per_cycle_kg,
            "aspiration": self.aspiration,
            "boost_pressure_Pa": self.boost_pressure_Pa,
            "supercharger_power_W": self.supercharger_power_W,
            "fuel": self.fuel,
            "equivalence_ratio": self.equivalence_ratio,
            "lambda_air": self.lambda_air,
            "fuel_air_ratio": self.fuel_air_ratio,
            "air_fuel_ratio": self.air_fuel_ratio,
            "operating_warnings": self.operating_warnings,
            "trace": self.trace,
        }


def simulate_piston_cycle(inputs: PistonCycleInputs,
                          trace_points: int = 240) -> PistonCycleResult:
    """March the closed-cycle first law and return indicated performance.

    Second-order midpoint integration in crank angle: a half-step predictor
    gives the mid-step pressure, which is then used for the full step. Using the
    *same* mid-step pressure for the work term in ``dU`` and for the accumulated
    indicated work makes the energy balance close to machine precision
    (``energy_residual_J`` ~ 0) while the midpoint rule keeps a reversible
    (motored) cycle returning to its start state to well under 0.1 %.
    """

    geom = CylinderGeometry(
        bore_m=inputs.bore_m,
        stroke_m=inputs.stroke_m,
        compression_ratio=inputs.compression_ratio,
        rod_ratio=inputs.rod_ratio,
    )

    gamma = inputs.gamma
    R = inputs.gas_constant_J_per_kg_K
    cv = R / (gamma - 1.0)

    # Trapped mass fixed from the BDC / IVC state.
    v_start = cylinder_volume(inputs.theta_start_deg * _DEG, geom)
    mass = inputs.intake_pressure_Pa * v_start / (R * inputs.intake_temperature_K)

    # Heat release: from fuel thermochemistry when a fuel is selected, else the
    # legacy raw heat-per-kg input. The trapped charge is treated as air for the
    # fuelling book-keeping (standard reduced-order assumption), so the injected
    # fuel mass is m_air * f and the chemical heat is fuel_mass * LHV * eta_comb.
    if inputs.fuel is not None:
        f_ratio = fuel_air_ratio(inputs.fuel, inputs.equivalence_ratio)
        q_per_kg = specific_heat_release_J_per_kg_charge(
            inputs.fuel, inputs.equivalence_ratio, inputs.combustion_efficiency,
        )
        fuel_mass_input = mass * f_ratio                  # injected fuel per cycle
        fuel_label = inputs.fuel.strip().casefold()
        lhv = get_fuel(inputs.fuel).lower_heating_value_J_per_kg
        phi = inputs.equivalence_ratio
        lam = lambda_from_phi(phi)
    else:
        q_per_kg = inputs.heat_release_J_per_kg
        fuel_mass_input = None                            # derived from heat below
        fuel_label = "manual"
        lhv = inputs.fuel_lhv_J_per_kg
        f_ratio = None
        phi = inputs.equivalence_ratio
        lam = lambda_from_phi(phi)
    q_total = mass * q_per_kg                             # J of fuel energy

    burn = lambda th: wiebe_burn_fraction(                 # noqa: E731
        th, inputs.combustion_start_deg, inputs.burn_duration_deg,
        inputs.wiebe_a, inputs.wiebe_m,
    )

    # March.
    theta = inputs.theta_start_deg
    end = inputs.theta_end_deg
    dth = inputs.d_theta_deg

    T = inputs.intake_temperature_K
    V = v_start
    p = mass * R * T / V
    U0 = mass * cv * T

    # Wall heat-transfer setup (Woschni). dt per crank-angle step from the
    # rotational speed; the IVC state is the Woschni reference state.
    omega = 2.0 * math.pi * inputs.rpm / 60.0
    dt_step = (dth * _DEG) / omega
    mean_piston_speed = 2.0 * inputs.stroke_m * (inputs.rpm / 60.0)
    displacement = geom.displacement_m3
    p_ref, v_ref, t_ref = inputs.intake_pressure_Pa, v_start, inputs.intake_temperature_K
    t_wall = inputs.wall_temperature_K
    ht_mult = inputs.wall_heat_transfer_multiplier
    bore = inputs.bore_m
    soc = inputs.combustion_start_deg

    work = 0.0
    wall_loss = 0.0
    peak_p = p
    peak_T = T
    x_prev = burn(theta)

    n_steps = max(1, int(round((end - theta) / dth)))
    every = max(1, n_steps // trace_points)
    trace: list[dict[str, float]] = [{
        "theta_deg": theta, "volume_m3": V, "pressure_Pa": p, "temperature_K": T,
    }]

    for k in range(1, n_steps + 1):
        theta_next = theta + dth
        theta_mid = theta + 0.5 * dth
        V_next = cylinder_volume(theta_next * _DEG, geom)
        V_mid = cylinder_volume(theta_mid * _DEG, geom)
        dV = V_next - V

        x_mid = burn(theta_mid)
        x_next = burn(theta_next)
        dQ_half = q_total * (x_mid - x_prev)   # heat released to mid-step
        dQ_full = q_total * (x_next - x_prev)  # heat released over full step

        # Wall heat loss over this step (Woschni, start-of-step state). Can be
        # negative early in compression when the cool charge is heated by the
        # walls. The same dQ_wall is used in dU and in the wall-loss tally, so
        # the energy balance still closes exactly.
        if ht_mult > 0.0:
            p_motored = p_ref * (v_ref / V) ** gamma
            w_gas = woschni_velocity(
                mean_piston_speed, p, p_motored, displacement,
                t_ref, p_ref, v_ref, burning=theta >= soc,
            )
            h = woschni_coefficient(bore, p, T, w_gas)
            dQ_wall = ht_mult * h * wall_surface_area_m2(V, bore) * (T - t_wall) * dt_step
        else:
            dQ_wall = 0.0

        # Predictor: advance to the mid-step with the start-of-step pressure,
        # then read the mid-step pressure.
        T_mid = T + (dQ_half - 0.5 * dQ_wall - p * (V_mid - V)) / (mass * cv)
        if T_mid <= 0.0:
            raise ValueError("Integration produced non-positive temperature; "
                             "check heat release and step size.")
        p_mid = mass * R * T_mid / V_mid

        # Corrector: full step with the mid-step pressure (used for both dU and
        # the work tally, so energy closes exactly).
        dU = dQ_full - dQ_wall - p_mid * dV
        T += dU / (mass * cv)
        if T <= 0.0:
            raise ValueError("Integration produced non-positive temperature; "
                             "check heat release and step size.")
        work += p_mid * dV
        wall_loss += dQ_wall

        V = V_next
        p = mass * R * T / V
        theta = theta_next
        x_prev = x_next

        if p > peak_p:
            peak_p = p
        if T > peak_T:
            peak_T = T
        if k % every == 0 or k == n_steps:
            trace.append({
                "theta_deg": theta, "volume_m3": V,
                "pressure_Pa": p, "temperature_K": T,
            })

    heat_released = q_total * (x_prev - burn(inputs.theta_start_deg))
    U_end = mass * cv * T
    # First-law closure: heat_in == work + wall_loss + delta_U (residual ~0).
    energy_residual = work - (heat_released - wall_loss - (U_end - U0))

    imep = work / displacement
    cycles_per_rev = 2.0 / inputs.strokes_per_cycle        # 4-stroke -> 0.5
    cycles_per_s = (inputs.rpm / 60.0) * cycles_per_rev
    power = work * inputs.cylinders * cycles_per_s
    omega = 2.0 * math.pi * inputs.rpm / 60.0
    torque = power / omega if omega > 0 else 0.0

    thermal_eff = (work / heat_released) if heat_released > 0 else 0.0
    air_standard_eff = 1.0 - 1.0 / inputs.compression_ratio ** (gamma - 1.0)

    # --- Pumping (gas-exchange) loop. Simple delta-p model: the piston works
    # against (p_exhaust - p_intake) over the displaced volume each cycle. When
    # throttled (p_intake < p_exhaust) this is a loss; at WOT it is ~zero. ---
    pmep = inputs.exhaust_pressure_Pa - inputs.intake_pressure_Pa
    pumping_work = pmep * displacement                  # loss (positive when throttled)
    net_work = work - pumping_work
    net_imep = net_work / displacement

    # --- Brake performance: net indicated minus friction, then minus the
    # supercharger's parasitic crank load (turbo/NA pay nothing here). ---
    cyl_rate = inputs.cylinders * cycles_per_s          # firing events per second
    fmep = chen_flynn_fmep_Pa(peak_p, mean_piston_speed, inputs.friction_multiplier)
    crank_brake_power = (net_imep - fmep) * displacement * cyl_rate

    sc_power = 0.0
    if inputs.aspiration == "supercharged":
        sc_power = supercharger_power_W(
            air_mass_flow_kg_s=mass * cyl_rate,
            inlet_temperature_K=inputs.intake_temperature_K,
            pressure_ratio=inputs.intake_pressure_Pa / inputs.ambient_pressure_Pa,
            efficiency=inputs.supercharger_efficiency,
            gas_constant_J_per_kg_K=R,
        )

    brake_power = crank_brake_power - sc_power
    brake_torque = brake_power / omega if omega > 0 else 0.0
    # Express the final brake output back as a BMEP / per-cycle work.
    bmep = brake_power / (displacement * cyl_rate) if cyl_rate > 0 else 0.0
    brake_work = bmep * displacement
    # Mechanical efficiency: brake / gross indicated (captures pumping, friction
    # and the supercharger parasitic).
    mech_eff = (brake_power / power) if power > 0 else 0.0
    fuel_power = heat_released * cyl_rate
    brake_thermal_eff = (brake_power / fuel_power) if fuel_power > 0 else 0.0

    # Fuel mass and BSFC. In fuel mode the injected fuel mass is known directly
    # from the air-fuel ratio (heat = fuel * LHV * eta_comb, so dividing heat by
    # LHV would under-count by eta_comb); in legacy mode it is heat / LHV.
    if fuel_mass_input is not None:
        fuel_per_cycle = fuel_mass_input
    else:
        fuel_per_cycle = heat_released / lhv
    fuel_flow_kg_s = fuel_per_cycle * cyl_rate
    # Fuelling descriptors reported alongside the performance.
    actual_far = (fuel_per_cycle / mass) if mass > 0 else 0.0
    actual_afr = (mass / fuel_per_cycle) if fuel_per_cycle > 0 else float("inf")
    bsfc_g_per_kWh = (
        fuel_flow_kg_s / brake_power * 3.6e9 if brake_power > 0 else float("inf")
    )

    # Operating limits (knock / smoke / lean misfire) for the converged point.
    # Only meaningful with a real fuel; the raw-heat path returns no flags.
    op_warnings = [
        w.to_dict() for w in evaluate_operating_limits(
            fuel_name=inputs.fuel,
            equivalence_ratio=phi,
            intake_temperature_K=inputs.intake_temperature_K,
            peak_pressure_Pa=peak_p,
            intake_pressure_Pa=inputs.intake_pressure_Pa,
            gamma=gamma,
        )
    ]

    return PistonCycleResult(
        indicated_work_J=work,
        imep_Pa=imep,
        indicated_power_W=power,
        indicated_torque_Nm=torque,
        thermal_efficiency=thermal_eff,
        air_standard_efficiency=air_standard_eff,
        peak_pressure_Pa=peak_p,
        peak_temperature_K=peak_T,
        trapped_mass_kg=mass,
        heat_released_J=heat_released,
        wall_heat_loss_J=wall_loss,
        energy_residual_J=energy_residual,
        pmep_Pa=pmep,
        pumping_work_J=pumping_work,
        net_imep_Pa=net_imep,
        net_indicated_work_J=net_work,
        fmep_Pa=fmep,
        bmep_Pa=bmep,
        brake_work_J=brake_work,
        brake_power_W=brake_power,
        brake_torque_Nm=brake_torque,
        mechanical_efficiency=mech_eff,
        brake_thermal_efficiency=brake_thermal_eff,
        bsfc_g_per_kWh=bsfc_g_per_kWh,
        fuel_mass_per_cycle_kg=fuel_per_cycle,
        aspiration=inputs.aspiration,
        boost_pressure_Pa=inputs.intake_pressure_Pa - inputs.ambient_pressure_Pa,
        supercharger_power_W=sc_power,
        fuel=fuel_label,
        equivalence_ratio=phi,
        lambda_air=lam,
        fuel_air_ratio=actual_far,
        air_fuel_ratio=actual_afr,
        operating_warnings=op_warnings,
        trace=trace,
    )

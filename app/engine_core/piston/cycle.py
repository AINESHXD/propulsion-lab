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
from dataclasses import dataclass, field, replace
from typing import Any

from app.engine_core.piston.aspiration import (
    ASPIRATION_MODES,
    compressor_power_W,
    supercharger_power_W,
    turbine_back_pressure_Pa,
)
from app.engine_core.piston.friction import chen_flynn_fmep_Pa
from app.engine_core.piston.fuel import (
    fuel_air_ratio,
    get_fuel,
    lambda_from_phi,
    specific_heat_release_J_per_kg_charge,
)
from app.engine_core.piston.geometry import CylinderGeometry, cylinder_volume
from app.engine_core.piston.layout import EngineLayout
from app.engine_core.piston.limits import evaluate_operating_limits
from app.engine_core.piston.valvetrain import (
    ValveGeometry,
    ValveTiming,
    breathing_report,
    trapped_charge_split,
)
from app.engine_core.piston.heat_transfer import (
    wall_surface_area_m2,
    woschni_coefficient,
    woschni_velocity,
)
from app.engine_core.piston import thermo
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
    # Turbocharger. The compressor costs the crank nothing, but the turbine
    # has to expand the exhaust to drive it, and that back-pressure is real.
    compressor_efficiency: float = 0.72      # isentropic, turbo compressor side
    turbine_efficiency: float = 0.70         # isentropic, turbine side
    turbo_mechanical_efficiency: float = 0.98

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

    # Integration window (closed cycle: BDC -> BDC across TDC=0). Used only when
    # no valve timing is supplied; a cam overrides both ends below.
    theta_start_deg: float = -180.0
    theta_end_deg: float = 180.0
    d_theta_deg: float = 0.5

    # --- Custom engine builder (all optional; None reproduces the plain
    # single-representative-cylinder behaviour exactly). ---
    #
    # ``layout`` describes how the cylinders are arranged. It does not change
    # the thermodynamics -- every cylinder still runs the same cycle -- but it
    # scales friction with bearing and head count, and it carries the firing
    # and balance analysis through to the result.
    layout: EngineLayout | None = None
    # ``valve_timing`` moves the integration window off BDC: compression starts
    # at intake-valve close and expansion ends at exhaust-valve open. This is
    # what makes the effective compression ratio diverge from the geometric one.
    valve_timing: ValveTiming | None = None
    # ``valve_geometry`` sizes the ports, which limits how well the cylinder
    # breathes (volumetric efficiency) and how hard it has to push the exhaust
    # out (back-pressure).
    valve_geometry: ValveGeometry | None = None
    # Exhaust temperature used to size the residual left in the clearance
    # volume. Filled in automatically by the two-pass solve below; 0 means
    # "no residual", which is what the first pass runs with.
    residual_reference_temperature_K: float | None = None
    # Temperature-dependent specific heats. Off by default so the constant
    # -gamma behaviour is preserved exactly; on, cp/cv/gamma follow the
    # charge temperature and composition and the integrator marches internal
    # energy instead of temperature.
    variable_specific_heats: bool = False
    # Two-zone combustion: track burned and unburned gas separately through
    # the burn, so the end-gas temperature that drives knock is a computed
    # quantity rather than a proxy. Implies variable specific heats.
    two_zone_combustion: bool = False

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
        if not 0.0 < self.compressor_efficiency <= 1.0:
            raise ValueError("compressor_efficiency must be in (0, 1].")
        if not 0.0 < self.turbine_efficiency <= 1.0:
            raise ValueError("turbine_efficiency must be in (0, 1].")
        if not 0.0 < self.turbo_mechanical_efficiency <= 1.0:
            raise ValueError("turbo_mechanical_efficiency must be in (0, 1].")
        if self.equivalence_ratio <= 0.0:
            raise ValueError("equivalence_ratio (phi) must be positive.")
        if not 0.0 < self.combustion_efficiency <= 1.0:
            raise ValueError("combustion_efficiency must be in (0, 1].")
        if self.fuel is not None:
            get_fuel(self.fuel)              # validates the name (raises ValueError)
        if self.layout is not None and self.layout.cylinders != self.cylinders:
            raise ValueError(
                f"Layout describes {self.layout.cylinders} cylinders but the "
                f"cycle was given {self.cylinders}; they must agree."
            )
        if self.layout is not None and self.layout.strokes_per_cycle != self.strokes_per_cycle:
            raise ValueError(
                "Layout and cycle disagree on strokes per cycle; they must agree."
            )


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

    # --- Turbocharger back-pressure. A turbo makes its boost by expanding the
    # exhaust across a turbine, which raises the pressure the piston pushes
    # against; these report what that costs. ---
    exhaust_pressure_Pa: float = 1.0e5       # manifold pressure the piston pushes against
    compressor_power_W: float = 0.0          # shaft power the charger absorbs
    turbine_pressure_ratio: float | None = None   # expansion the turbine needs
    boost_sustainable: bool = True           # False when exhaust enthalpy runs out

    # --- Residual gas left in the clearance volume, and the exhaust state
    # that sized it. ---
    exhaust_temperature_K: float = 0.0       # gas temperature at exhaust-valve open
    residual_fraction: float | None = None   # burned gas share of the trapped charge
    fresh_mass_kg: float | None = None       # trapped mass that can actually burn
    mixed_temperature_K: float | None = None # charge temperature after mixing

    # --- Variable specific heats / two-zone combustion. ---
    variable_specific_heats: bool = False
    two_zone_combustion: bool = False
    mean_gamma: float | None = None          # cycle-average ratio of specific heats
    peak_unburned_temperature_K: float | None = None   # the end-gas that knocks
    peak_burned_temperature_K: float | None = None     # behind the flame front

    # --- Builder extras. None when no valvetrain / layout was supplied, so a
    # plain call reports exactly what it always did. ---
    effective_compression_ratio: float | None = None   # V(IVC) / V_TDC
    effective_expansion_ratio: float | None = None     # V(EVO) / V_TDC
    volumetric_efficiency: float | None = None         # valve-limited breathing
    inlet_mach_index: float | None = None              # Taylor Z, intake side
    exhaust_mach_index: float | None = None            # Taylor Z, exhaust side
    valve_overlap_deg: float | None = None
    closed_period_deg: float | None = None             # crank degrees integrated
    breathing_verdict: str | None = None
    layout: dict[str, Any] | None = None               # firing + balance report
    layout_friction_scale: float | None = None
    # Resolved geometry, echoed back so a builder that specified a capacity
    # can see the bore and stroke it actually got.
    bore_m: float | None = None
    stroke_m: float | None = None
    total_displacement_m3: float | None = None

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
            "exhaust_pressure_Pa": self.exhaust_pressure_Pa,
            "compressor_power_W": self.compressor_power_W,
            "turbine_pressure_ratio": self.turbine_pressure_ratio,
            "boost_sustainable": self.boost_sustainable,
            "exhaust_temperature_K": self.exhaust_temperature_K,
            "residual_fraction": self.residual_fraction,
            "fresh_mass_kg": self.fresh_mass_kg,
            "mixed_temperature_K": self.mixed_temperature_K,
            "variable_specific_heats": self.variable_specific_heats,
            "two_zone_combustion": self.two_zone_combustion,
            "mean_gamma": self.mean_gamma,
            "peak_unburned_temperature_K": self.peak_unburned_temperature_K,
            "peak_burned_temperature_K": self.peak_burned_temperature_K,
            "fuel": self.fuel,
            "equivalence_ratio": self.equivalence_ratio,
            "lambda_air": self.lambda_air,
            "fuel_air_ratio": self.fuel_air_ratio,
            "air_fuel_ratio": self.air_fuel_ratio,
            "operating_warnings": self.operating_warnings,
            "effective_compression_ratio": self.effective_compression_ratio,
            "effective_expansion_ratio": self.effective_expansion_ratio,
            "volumetric_efficiency": self.volumetric_efficiency,
            "inlet_mach_index": self.inlet_mach_index,
            "exhaust_mach_index": self.exhaust_mach_index,
            "valve_overlap_deg": self.valve_overlap_deg,
            "closed_period_deg": self.closed_period_deg,
            "breathing_verdict": self.breathing_verdict,
            "layout": self.layout,
            "layout_friction_scale": self.layout_friction_scale,
            "bore_m": self.bore_m,
            "stroke_m": self.stroke_m,
            "total_displacement_m3": self.total_displacement_m3,
            "trace": self.trace,
        }


def simulate_piston_cycle(inputs: PistonCycleInputs,
                          trace_points: int = 240) -> PistonCycleResult:
    """Solve one operating point, accounting for residual gas.

    Residual mass depends on the exhaust state, which is an output of the
    solve, so a cam-equipped engine is solved twice: once to learn the
    exhaust temperature, then again with the residual that implies. The
    mixing itself closes algebraically, so two passes is exact rather than
    the first step of an iteration.
    """

    if inputs.valve_timing is None or inputs.residual_reference_temperature_K is not None:
        return _solve_cycle(inputs, trace_points)
    probe = _solve_cycle(replace(inputs, residual_reference_temperature_K=0.0), 4)
    return _solve_cycle(
        replace(inputs, residual_reference_temperature_K=probe.exhaust_temperature_K),
        trace_points,
    )


def _solve_cycle(inputs: PistonCycleInputs,
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

    # --- Gas properties. Both models are routed through the same closures so
    # the marching code below is written once. With variable specific heats the
    # properties follow temperature and burned fraction; without, they collapse
    # to the constants and the arithmetic is identical to before. ---
    gamma = inputs.gamma
    R = inputs.gas_constant_J_per_kg_K
    cv = R / (gamma - 1.0)

    if inputs.variable_specific_heats:
        def cv_at(temp: float, burned: float) -> float:
            return thermo.cv_J_per_kg_K(temp, burned)

        def R_at(burned: float) -> float:
            return thermo.mixture_gas_constant(burned)

        def u_at(temp: float, burned: float) -> float:
            return thermo.internal_energy_J_per_kg(temp, burned)

        def T_at(energy: float, burned: float, guess: float) -> float:
            return thermo.temperature_from_internal_energy(energy, burned, guess_K=guess)

        def gamma_at(temp: float, burned: float) -> float:
            return thermo.gamma(temp, burned)
    else:
        def cv_at(temp: float, burned: float) -> float:
            return cv

        def R_at(burned: float) -> float:
            return R

        def u_at(temp: float, burned: float) -> float:
            return cv * temp

        def T_at(energy: float, burned: float, guess: float) -> float:
            return energy / cv

        def gamma_at(temp: float, burned: float) -> float:
            return gamma

    # --- Valve timing sets the integration window. Without a cam the window is
    # the classic BDC-to-BDC span; with one, compression starts at intake-valve
    # close and expansion ends at exhaust-valve open. Everything downstream --
    # trapped mass, effective compression ratio, blowdown -- follows from that
    # rather than needing its own model. ---
    if inputs.valve_timing is not None:
        theta_start_deg = inputs.valve_timing.ivc_theta_deg
        theta_end_deg = inputs.valve_timing.evo_theta_deg
    else:
        theta_start_deg = inputs.theta_start_deg
        theta_end_deg = inputs.theta_end_deg

    mean_piston_speed = 2.0 * inputs.stroke_m * (inputs.rpm / 60.0)

    # --- Breathing. A sized head limits how much charge actually gets in and
    # how hard the exhaust is to push out. Without one, the cylinder is assumed
    # to fill to manifold conditions and the exhaust to sit where the caller
    # put it. ---
    breathing: dict[str, Any] | None = None
    volumetric_efficiency = 1.0
    exhaust_pressure_Pa = inputs.exhaust_pressure_Pa
    if inputs.valve_geometry is not None:
        breathing = breathing_report(
            geom=geom,
            timing=inputs.valve_timing or ValveTiming(),
            valves=inputs.valve_geometry,
            mean_piston_speed_m_s=mean_piston_speed,
            intake_temperature_K=inputs.intake_temperature_K,
            ambient_pressure_Pa=inputs.ambient_pressure_Pa,
            gamma=gamma,
            gas_constant_J_per_kg_K=R,
        )
        volumetric_efficiency = breathing["volumetric_efficiency"]
        exhaust_pressure_Pa = breathing["exhaust_pressure_Pa"]

    # Trapped mass fixed from the IVC state, scaled by how well the head
    # breathes. A choked inlet traps less charge, so the cylinder starts the
    # compression stroke below manifold pressure.
    v_start = cylinder_volume(theta_start_deg * _DEG, geom)

    # --- Residual gas. The piston cannot sweep the clearance volume, so burned
    # gas from the last cycle is still in there when the intake shuts. It is hot,
    # which raises the charge temperature, and it is already burned, so it
    # dilutes: only the fresh part carries fuel. Valve overlap decides whether
    # boost scavenges it out or throttling pulls more of it back in. ---
    residual_fraction: float | None = None
    t_ref_exhaust = inputs.residual_reference_temperature_K or 0.0
    if inputs.valve_timing is not None and t_ref_exhaust > 0.0:
        split = trapped_charge_split(
            ivc_volume_m3=v_start,
            clearance_volume_m3=geom.clearance_m3,
            intake_pressure_Pa=inputs.intake_pressure_Pa,
            intake_temperature_K=inputs.intake_temperature_K,
            exhaust_pressure_Pa=exhaust_pressure_Pa,
            exhaust_temperature_K=t_ref_exhaust,
            valve_overlap_deg=inputs.valve_timing.valve_overlap_deg,
            volumetric_efficiency=volumetric_efficiency,
            gas_constant_J_per_kg_K=R,
        )
        mass = split["total_mass_kg"]
        mass_fresh = split["fresh_mass_kg"]
        residual_fraction = split["residual_fraction"]
        t_ivc = split["mixed_temperature_K"]
    else:
        mass = (volumetric_efficiency * inputs.intake_pressure_Pa * v_start
                / (R * inputs.intake_temperature_K))
        mass_fresh = mass
        t_ivc = inputs.intake_temperature_K

    # Heat release: from fuel thermochemistry when a fuel is selected, else the
    # legacy raw heat-per-kg input. The trapped charge is treated as air for the
    # fuelling book-keeping (standard reduced-order assumption), so the injected
    # fuel mass is m_air * f and the chemical heat is fuel_mass * LHV * eta_comb.
    if inputs.fuel is not None:
        f_ratio = fuel_air_ratio(inputs.fuel, inputs.equivalence_ratio)
        q_per_kg = specific_heat_release_J_per_kg_charge(
            inputs.fuel, inputs.equivalence_ratio, inputs.combustion_efficiency,
        )
        fuel_mass_input = mass_fresh * f_ratio            # injected fuel per cycle
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
    # Only the fresh charge carries fuel: the residual is already burned, so a
    # dilute cylinder releases less heat for the same volume.
    q_total = mass_fresh * q_per_kg                       # J of fuel energy

    burn = lambda th: wiebe_burn_fraction(                 # noqa: E731
        th, inputs.combustion_start_deg, inputs.burn_duration_deg,
        inputs.wiebe_a, inputs.wiebe_m,
    )

    # March.
    theta = theta_start_deg
    end = theta_end_deg
    dth = inputs.d_theta_deg

    T = t_ivc                    # fresh charge and hot residual, after mixing
    V = v_start
    x_burn = burn(theta)                       # burned mass fraction at IVC
    p = mass * R_at(x_burn) * T / V
    U0 = mass * u_at(T, x_burn)
    U = U0                                     # internal energy is what we march

    # Wall heat-transfer setup (Woschni). dt per crank-angle step from the
    # rotational speed; the IVC state is the Woschni reference state.
    omega = 2.0 * math.pi * inputs.rpm / 60.0
    dt_step = (dth * _DEG) / omega
    displacement = geom.displacement_m3
    p_ref, v_ref, t_ref = p, v_start, t_ivc
    t_wall = inputs.wall_temperature_K
    ht_mult = inputs.wall_heat_transfer_multiplier
    bore = inputs.bore_m
    soc = inputs.combustion_start_deg

    work = 0.0
    wall_loss = 0.0
    peak_p = p
    peak_T = T
    x_prev = burn(theta)

    # Two-zone tracking. The unburned zone is compressed isentropically from
    # the intake-valve-close state, so its reference is fixed here.
    two_zone = inputs.two_zone_combustion and inputs.variable_specific_heats
    ivc_T, ivc_p = T, p
    T_unburned = T
    T_burned = T
    peak_unburned_T = T
    peak_burned_T = T
    burned_volume_fraction = 0.0
    gamma_sum = gamma_at(T, x_burn)
    gamma_count = 1

    n_steps = max(1, int(round((end - theta) / dth)))
    every = max(1, n_steps // trace_points)

    def _entropy(temp: float, vol: float, burned: float = 0.0) -> float:
        # Specific entropy of the ideal-gas charge to an arbitrary datum
        # (s = c_v ln T + R ln v, v = V/m); only differences matter for the
        # T–s diagram, so the datum is free.
        return cv_at(temp, burned) * math.log(temp) + R_at(burned) * math.log(vol / mass)

    trace: list[dict[str, float]] = [{
        "theta_deg": theta, "volume_m3": V, "pressure_Pa": p, "temperature_K": T,
        "entropy_J_per_kg_K": _entropy(T, V, x_burn),
        "burned_fraction": x_burn,
        **({"burned_volume_fraction": 0.0,
            "unburned_temperature_K": T,
            "burned_temperature_K": T} if two_zone else {}),
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
            p_motored = p_ref * (v_ref / V) ** gamma_at(T, x_burn)
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
        U_mid = U + dQ_half - 0.5 * dQ_wall - p * (V_mid - V)
        # Explicit estimate of the new temperature, used to seed the
        # inversion so Newton usually converges in a single step.
        T_mid = T_at(U_mid / mass, x_mid, T + (U_mid - U) / (mass * cv_at(T, x_burn)))
        if T_mid <= 0.0:
            raise ValueError("Integration produced non-positive temperature; "
                             "check heat release and step size.")
        p_mid = mass * R_at(x_mid) * T_mid / V_mid

        # Corrector: full step with the mid-step pressure (used for both dU and
        # the work tally, so energy closes exactly).
        dU = dQ_full - dQ_wall - p_mid * dV
        U += dU
        T = T_at(U / mass, x_next, T + dU / (mass * cv_at(T, x_burn)))
        if T <= 0.0:
            raise ValueError("Integration produced non-positive temperature; "
                             "check heat release and step size.")
        work += p_mid * dV
        wall_loss += dQ_wall

        V = V_next
        x_burn = x_next
        p = mass * R_at(x_burn) * T / V

        if two_zone:
            if thermo.TWO_ZONE_MIN_FRACTION < x_burn < 1.0 - thermo.TWO_ZONE_MIN_FRACTION:
                # Mid-burn: solve the shared-pressure split. The bulk energy the
                # march arrived at is what the two zones have to add up to.
                p, T_unburned, T_burned = thermo.two_zone_state(
                    volume_m3=V, internal_energy_J=U, mass_kg=mass,
                    burned_fraction=x_burn,
                    unburned_reference_temperature_K=ivc_T,
                    unburned_reference_pressure_Pa=ivc_p,
                    pressure_guess_Pa=p,
                )
                v_unburned = (1.0 - x_burn) * mass * thermo.R_AIR * T_unburned / p
                burned_volume_fraction = min(1.0, max(0.0, 1.0 - v_unburned / V))
            elif x_burn <= thermo.TWO_ZONE_MIN_FRACTION:
                # Before the flame arrives the whole charge is unburned end-gas.
                T_unburned = T
                T_burned = T
                burned_volume_fraction = 0.0
            else:
                # Fully burned: one zone again, and the end-gas is gone.
                T_burned = T
                burned_volume_fraction = 1.0
            if x_burn < 1.0 - thermo.TWO_ZONE_MIN_FRACTION:
                peak_unburned_T = max(peak_unburned_T, T_unburned)
            peak_burned_T = max(peak_burned_T, T_burned)

        gamma_sum += gamma_at(T, x_burn)
        gamma_count += 1
        theta = theta_next
        x_prev = x_next

        if p > peak_p:
            peak_p = p
        if T > peak_T:
            peak_T = T
        if k % every == 0 or k == n_steps:
            point = {
                "theta_deg": theta, "volume_m3": V,
                "pressure_Pa": p, "temperature_K": T,
                "entropy_J_per_kg_K": _entropy(T, V, x_burn),
                "burned_fraction": x_burn,
            }
            if two_zone:
                # The console draws the flame front from these.
                point["burned_volume_fraction"] = burned_volume_fraction
                point["unburned_temperature_K"] = T_unburned
                point["burned_temperature_K"] = T_burned
            trace.append(point)

    heat_released = q_total * (x_prev - burn(theta_start_deg))
    U_end = mass * u_at(T, x_prev)
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

    cyl_rate = inputs.cylinders * cycles_per_s          # firing events per second

    # Fuel mass per cycle. In fuel mode it is known directly from the air-fuel
    # ratio (heat = fuel * LHV * eta_comb, so dividing heat by LHV would
    # under-count by eta_comb); in legacy mode it is heat / LHV.
    if fuel_mass_input is not None:
        fuel_per_cycle = fuel_mass_input
    else:
        fuel_per_cycle = heat_released / lhv

    # --- Turbocharger back-pressure. A turbo pays nothing at the crank, but its
    # turbine can only make shaft power by expanding the exhaust across itself,
    # and that raises the pressure the piston pushes against. Solving the shaft
    # power balance gives the expansion ratio the turbine needs, which sits on
    # top of whatever restriction is downstream of it. ---
    turbine_pressure_ratio: float | None = None
    boost_sustainable = True
    compressor_power = 0.0
    if inputs.aspiration == "turbocharged":
        pressure_ratio = inputs.intake_pressure_Pa / inputs.ambient_pressure_Pa
        if pressure_ratio > 1.0:
            compressor_power = compressor_power_W(
                air_mass_flow_kg_s=mass * cyl_rate,
                inlet_temperature_K=inputs.intake_temperature_K,
                pressure_ratio=pressure_ratio,
                efficiency=inputs.compressor_efficiency,
                gas_constant_J_per_kg_K=R,
            )
            exhaust_pressure_Pa, turbine_pressure_ratio, boost_sustainable = (
                turbine_back_pressure_Pa(
                    compressor_power_W_=compressor_power,
                    # The exhaust carries the fuel out as well as the air.
                    exhaust_mass_flow_kg_s=(mass + fuel_per_cycle) * cyl_rate,
                    exhaust_temperature_K=T,          # gas state at exhaust-valve open
                    downstream_pressure_Pa=exhaust_pressure_Pa,
                    turbine_efficiency=inputs.turbine_efficiency,
                    mechanical_efficiency=inputs.turbo_mechanical_efficiency,
                )
            )

    # --- Pumping (gas-exchange) loop. Simple delta-p model: the piston works
    # against (p_exhaust - p_intake) over the displaced volume each cycle. When
    # throttled (p_intake < p_exhaust) this is a loss; at WOT it is ~zero. A
    # well-matched turbo can run manifold pressure above exhaust pressure, which
    # makes this term negative -- the gas exchange then helps the piston. ---
    pmep = exhaust_pressure_Pa - inputs.intake_pressure_Pa
    pumping_work = pmep * displacement                  # loss (positive when throttled)
    net_work = work - pumping_work
    net_imep = net_work / displacement

    # --- Brake performance: net indicated minus friction, then minus the
    # supercharger's parasitic crank load (turbo/NA pay nothing here). ---
    # A layout with more mains to rub and more heads to drive costs more
    # friction; without one the scale is exactly 1 and nothing changes.
    layout_friction = inputs.layout.friction_scale() if inputs.layout is not None else 1.0
    fmep = chen_flynn_fmep_Pa(
        peak_p, mean_piston_speed, inputs.friction_multiplier * layout_friction,
    )
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

    fuel_flow_kg_s = fuel_per_cycle * cyl_rate
    # Fuelling descriptors reported alongside the performance.
    actual_far = (fuel_per_cycle / mass_fresh) if mass_fresh > 0 else 0.0
    actual_afr = (mass_fresh / fuel_per_cycle) if fuel_per_cycle > 0 else float("inf")
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
            # With two zones the end gas is a tracked quantity, not an estimate.
            measured_end_gas_temperature_K=peak_unburned_T if two_zone else None,
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
        exhaust_pressure_Pa=exhaust_pressure_Pa,
        compressor_power_W=compressor_power,
        turbine_pressure_ratio=turbine_pressure_ratio,
        boost_sustainable=boost_sustainable,
        exhaust_temperature_K=T,
        residual_fraction=residual_fraction,
        fresh_mass_kg=mass_fresh if residual_fraction is not None else None,
        mixed_temperature_K=t_ivc if residual_fraction is not None else None,
        variable_specific_heats=inputs.variable_specific_heats,
        two_zone_combustion=two_zone,
        mean_gamma=(gamma_sum / gamma_count) if inputs.variable_specific_heats else None,
        peak_unburned_temperature_K=peak_unburned_T if two_zone else None,
        peak_burned_temperature_K=peak_burned_T if two_zone else None,
        fuel=fuel_label,
        equivalence_ratio=phi,
        lambda_air=lam,
        fuel_air_ratio=actual_far,
        air_fuel_ratio=actual_afr,
        operating_warnings=op_warnings,
        effective_compression_ratio=(
            breathing["effective_compression_ratio"] if breathing
            else (cylinder_volume(theta_start_deg * _DEG, geom) / geom.volume_min_m3
                  if inputs.valve_timing is not None else None)
        ),
        effective_expansion_ratio=(
            breathing["effective_expansion_ratio"] if breathing
            else (cylinder_volume(theta_end_deg * _DEG, geom) / geom.volume_min_m3
                  if inputs.valve_timing is not None else None)
        ),
        volumetric_efficiency=breathing["volumetric_efficiency"] if breathing else None,
        inlet_mach_index=breathing["inlet_mach_index"] if breathing else None,
        exhaust_mach_index=breathing["exhaust_mach_index"] if breathing else None,
        valve_overlap_deg=(
            inputs.valve_timing.valve_overlap_deg if inputs.valve_timing else None
        ),
        closed_period_deg=theta_end_deg - theta_start_deg,
        breathing_verdict=breathing["breathing_verdict"] if breathing else None,
        layout=inputs.layout.to_dict() if inputs.layout is not None else None,
        layout_friction_scale=layout_friction if inputs.layout is not None else None,
        bore_m=inputs.bore_m,
        stroke_m=inputs.stroke_m,
        total_displacement_m3=displacement * inputs.cylinders,
        trace=trace,
    )

"""Valve timing, breathing and exhaust restriction.

The cycle integrator marches the *closed* part of the cycle, so the valves set
its boundaries: compression begins when the intake valve shuts and expansion
ends when the exhaust valve cracks open. Until now those boundaries were pinned
at BDC either side of TDC, which quietly assumes the valves close and open
exactly at bottom dead centre. Real engines do neither, and the difference is
not cosmetic.

What follows from the timing
----------------------------
* **Effective compression ratio.** The charge is only trapped from intake-valve
  close onward, so the ratio that actually does thermodynamic work is
  ``V(IVC) / V_TDC``, not the geometric ``V_BDC / V_TDC``. Closing the intake
  late throws part of the charge back out of the cylinder and drops the
  effective ratio below the geometric one. That is the whole Miller/Atkinson
  idea, and here it is a consequence of the geometry rather than a special mode.
* **Expansion ratio.** Opening the exhaust early ends the useful stroke sooner,
  so expansion is shorter than compression. Blowdown loss is what you trade for
  getting the exhaust out in time.
* **Trapped mass.** Mass follows from the state at IVC, so late closing traps
  less. No extra model is needed for that part.

What needs a correlation
------------------------
How well the engine *breathes* is not pure geometry, so it needs a model. The
classic reduced-order handle is Taylor's **inlet Mach index**::

    Z = (A_piston * Sp_mean) / (A_inlet * c)

the ratio of the volumetric demand the piston makes to what the inlet valve can
pass at sonic conditions. Volumetric efficiency is roughly flat while ``Z`` is
small and falls away once ``Z`` passes a knee near 0.5, because the inlet is
choking. The falloff used here is a smooth quadratic past that knee: it has the
right shape and the right knee, and it is **a reduced-order correlation, not a
measured flow map for any engine**. The same index on the exhaust side drives a
back-pressure rise. Both coefficients are stated below and are model
parameters.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.engine_core.piston.geometry import CylinderGeometry, cylinder_volume

_DEG = math.pi / 180.0

# Inlet Mach index at which volumetric efficiency starts falling away. Below the
# knee the inlet is not the limit; above it, the valve is choking the cylinder.
_Z_KNEE = 0.50
# Curvature of the falloff past the knee, anchored so Z = 1.0 costs ~30% of the
# breathing. Model parameter.
_Z_FALLOFF = 1.20
# Floor on the valve-limited volumetric efficiency, so an absurd geometry still
# returns a solvable (if terrible) engine rather than zero mass.
_VE_FLOOR = 0.15

# Exhaust back-pressure rise per unit of squared exhaust Mach index, at nominal
# restriction. Model parameter: a restriction index of 1.0 and an exhaust Mach
# index of 1.0 puts the exhaust manifold 30% over ambient.
_BACK_PRESSURE_COEFF = 0.30

# Representative exhaust gas temperature for the exhaust-side speed of sound.
# The blowdown temperature varies through the stroke; a single representative
# value is the reduced-order call.
_EXHAUST_TEMPERATURE_K = 900.0

_GAMMA_AIR = 1.4
_R_AIR = 287.0


@dataclass(slots=True, frozen=True)
class ValveTiming:
    """Valve events, in the usual workshop convention (all positive numbers).

    ``ivo`` and ``evc`` are quoted before/after TDC, ``ivc`` and ``evo``
    after/before BDC, which is how a cam card reads.
    """

    intake_open_btdc_deg: float = 10.0
    intake_close_abdc_deg: float = 40.0
    exhaust_open_bbdc_deg: float = 45.0
    exhaust_close_atdc_deg: float = 10.0

    def __post_init__(self) -> None:
        for name, value in (
            ("intake_open_btdc_deg", self.intake_open_btdc_deg),
            ("intake_close_abdc_deg", self.intake_close_abdc_deg),
            ("exhaust_open_bbdc_deg", self.exhaust_open_bbdc_deg),
            ("exhaust_close_atdc_deg", self.exhaust_close_atdc_deg),
        ):
            if not -60.0 <= value <= 120.0:
                raise ValueError(f"{name} must be in [-60, 120] deg.")
        # The integrator needs a meaningful closed period either side of TDC to
        # compress the charge, burn it and expand it. Below ~120 deg total there
        # is not enough crank angle left for that to mean anything.
        if self.closed_period_deg <= 120.0:
            raise ValueError(
                "Valve timing leaves too little closed cycle to integrate "
                f"({self.closed_period_deg:.0f} deg): the intake must close "
                "well before the exhaust opens."
            )

    @property
    def valve_overlap_deg(self) -> float:
        """Crank degrees with both valves off their seats, around gas-exchange TDC."""

        return self.intake_open_btdc_deg + self.exhaust_close_atdc_deg

    @property
    def ivc_theta_deg(self) -> float:
        """Intake-valve close on the solver's crank axis (firing TDC = 0)."""

        return -180.0 + self.intake_close_abdc_deg

    @property
    def evo_theta_deg(self) -> float:
        """Exhaust-valve open on the solver's crank axis (firing TDC = 0)."""

        return 180.0 - self.exhaust_open_bbdc_deg

    @property
    def closed_period_deg(self) -> float:
        """Crank degrees the integrator actually marches (IVC to EVO)."""

        return self.evo_theta_deg - self.ivc_theta_deg


@dataclass(slots=True, frozen=True)
class ValveGeometry:
    """Port and valve sizing, expressed as ratios of the bore.

    Ratios rather than millimetres so the geometry scales with any bore, and so
    a four-valve head and a two-valve head can be compared honestly: four small
    valves beat two big ones on curtain area, which is the entire reason
    multi-valve heads exist.
    """

    intake_valves_per_cylinder: int = 2
    exhaust_valves_per_cylinder: int = 2
    intake_valve_diameter_ratio: float = 0.38     # D_intake / bore
    exhaust_valve_diameter_ratio: float = 0.33    # D_exhaust / bore
    max_lift_ratio: float = 0.25                  # max lift / valve diameter
    discharge_coefficient: float = 0.35           # mean C_d over the lift curve
    exhaust_restriction: float = 1.0              # 0 = open pipe, 1 = nominal, 2+ = restrictive

    def __post_init__(self) -> None:
        if self.intake_valves_per_cylinder < 1 or self.exhaust_valves_per_cylinder < 1:
            raise ValueError("Each cylinder needs at least one intake and one exhaust valve.")
        if self.intake_valves_per_cylinder > 4 or self.exhaust_valves_per_cylinder > 4:
            raise ValueError("More than four valves per port is outside this model.")
        for name, value in (
            ("intake_valve_diameter_ratio", self.intake_valve_diameter_ratio),
            ("exhaust_valve_diameter_ratio", self.exhaust_valve_diameter_ratio),
        ):
            if not 0.15 <= value <= 0.60:
                raise ValueError(f"{name} must be in [0.15, 0.60] of the bore.")
        if not 0.10 <= self.max_lift_ratio <= 0.40:
            raise ValueError("max_lift_ratio must be in [0.10, 0.40] of valve diameter.")
        if not 0.15 <= self.discharge_coefficient <= 0.80:
            raise ValueError("discharge_coefficient must be in [0.15, 0.80].")
        if not 0.0 <= self.exhaust_restriction <= 4.0:
            raise ValueError("exhaust_restriction must be in [0, 4].")

    def _curtain_area_m2(self, bore_m: float, count: int, diameter_ratio: float) -> float:
        """Effective flow area at max lift: the cylindrical curtain under the valve."""

        d_valve = diameter_ratio * bore_m
        lift = self.max_lift_ratio * d_valve
        return count * math.pi * d_valve * lift * self.discharge_coefficient

    def intake_flow_area_m2(self, bore_m: float) -> float:
        return self._curtain_area_m2(
            bore_m, self.intake_valves_per_cylinder, self.intake_valve_diameter_ratio,
        )

    def exhaust_flow_area_m2(self, bore_m: float) -> float:
        return self._curtain_area_m2(
            bore_m, self.exhaust_valves_per_cylinder, self.exhaust_valve_diameter_ratio,
        )


# ------------------------------------------------------------------ physics

def effective_compression_ratio(geom: CylinderGeometry, ivc_theta_deg: float) -> float:
    """Compression ratio the charge actually sees, ``V(IVC) / V_TDC``.

    Equals the geometric ratio only when the intake closes exactly at BDC.
    Closing later spills charge back out and lowers it -- the Miller effect.
    """

    return cylinder_volume(ivc_theta_deg * _DEG, geom) / geom.volume_min_m3


def effective_expansion_ratio(geom: CylinderGeometry, evo_theta_deg: float) -> float:
    """Expansion ratio actually realised, ``V(EVO) / V_TDC``.

    Opening the exhaust before BDC cuts the stroke short, so this sits below the
    geometric ratio. An engine whose expansion ratio exceeds its compression
    ratio is running an Atkinson-style cycle.
    """

    return cylinder_volume(evo_theta_deg * _DEG, geom) / geom.volume_min_m3


def speed_of_sound_m_s(temperature_K: float,
                       gamma: float = _GAMMA_AIR,
                       gas_constant_J_per_kg_K: float = _R_AIR) -> float:
    if temperature_K <= 0.0:
        raise ValueError("temperature_K must be positive.")
    return math.sqrt(gamma * gas_constant_J_per_kg_K * temperature_K)


def mach_index(piston_area_m2: float,
               mean_piston_speed_m_s: float,
               flow_area_m2: float,
               speed_of_sound: float) -> float:
    """Taylor inlet Mach index: demanded volume flow over available valve flow.

    Dimensionless. Small means the valve is not the limit; past ~0.5 the port
    starts choking the cylinder.
    """

    if flow_area_m2 <= 0.0 or speed_of_sound <= 0.0:
        raise ValueError("flow_area_m2 and speed_of_sound must be positive.")
    if mean_piston_speed_m_s < 0.0:
        raise ValueError("mean_piston_speed_m_s must be non-negative.")
    return (piston_area_m2 * mean_piston_speed_m_s) / (flow_area_m2 * speed_of_sound)


def volumetric_efficiency_from_mach_index(z: float) -> float:
    """Valve-limited volumetric efficiency for an inlet Mach index ``z``.

    Flat below the knee, quadratic falloff above it, floored so the solver
    always has mass to work with. Reduced-order correlation, not a flow map.
    """

    if z < 0.0:
        raise ValueError("Mach index must be non-negative.")
    excess = max(0.0, z - _Z_KNEE)
    return max(_VE_FLOOR, min(1.0, 1.0 - _Z_FALLOFF * excess * excess))


def exhaust_back_pressure_Pa(ambient_pressure_Pa: float,
                             exhaust_mach_index: float,
                             restriction: float = 1.0) -> float:
    """Exhaust manifold pressure: ambient plus the cost of pushing gas out.

    Rises with the square of the exhaust-side Mach index and linearly with the
    restriction index, so a free-flowing system at low speed sits at ambient and
    a restrictive one at high speed costs real pumping work.
    """

    if ambient_pressure_Pa <= 0.0:
        raise ValueError("ambient_pressure_Pa must be positive.")
    if exhaust_mach_index < 0.0 or restriction < 0.0:
        raise ValueError("Mach index and restriction must be non-negative.")
    return ambient_pressure_Pa * (
        1.0 + _BACK_PRESSURE_COEFF * restriction * exhaust_mach_index ** 2
    )


# ---------------------------------------------------------------- residuals

# Overlap that counts as "a normal amount" when scaling the scavenging effect.
_OVERLAP_REFERENCE_DEG = 40.0
# How strongly overlap couples the intake/exhaust pressure ratio into the
# residual. Model parameter: at reference overlap and a pressure ratio of 2,
# scavenging removes roughly two thirds of the residual.
_SCAVENGE_COEFF = 1.0
# Residual cannot sensibly take more than half the cylinder in this model.
_MAX_RESIDUAL_FRACTION = 0.50


def residual_gas_mass_kg(clearance_volume_m3: float,
                         exhaust_pressure_Pa: float,
                         exhaust_temperature_K: float,
                         intake_pressure_Pa: float,
                         valve_overlap_deg: float,
                         gas_constant_J_per_kg_K: float = _R_AIR) -> float:
    """Burned gas left in the cylinder at the end of the exhaust stroke.

    The piston cannot sweep the clearance volume, so whatever is in it at
    exhaust-valve close stays for the next cycle::

        m_residual = p_exhaust * V_clearance / (R * T_exhaust)

    Valve overlap then decides what happens to it. While both valves are open,
    the intake and exhaust are connected, so the pressure ratio across them
    drives flow through the cylinder:

    * **Boosted** (intake above exhaust) — fresh charge blows the residual out.
      This is scavenging, and it is why overlap is worth having on a boosted or
      high-rpm engine.
    * **Throttled** (intake below exhaust) — exhaust is drawn *back* into the
      cylinder. This is the internal EGR that makes a throttled spark engine
      idle roughly and run dilute at part load.

    The strength of both is scaled by how much overlap there is. The
    exponential/linear pair below is a reduced-order shape with a stated
    coefficient, not a measured scavenging map.
    """

    if clearance_volume_m3 <= 0.0:
        raise ValueError("clearance_volume_m3 must be positive.")
    if exhaust_pressure_Pa <= 0.0 or intake_pressure_Pa <= 0.0:
        raise ValueError("Intake and exhaust pressures must be positive.")
    if exhaust_temperature_K <= 0.0:
        raise ValueError("exhaust_temperature_K must be positive.")

    base = exhaust_pressure_Pa * clearance_volume_m3 / (
        gas_constant_J_per_kg_K * exhaust_temperature_K
    )
    overlap = max(0.0, valve_overlap_deg) / _OVERLAP_REFERENCE_DEG
    ratio = intake_pressure_Pa / exhaust_pressure_Pa

    if ratio >= 1.0:
        # Scavenging: decays away as boost and overlap rise.
        return base * math.exp(-_SCAVENGE_COEFF * overlap * (ratio - 1.0))
    # Backflow: throttling pulls exhaust back in through the overlap window.
    return base * (1.0 + _SCAVENGE_COEFF * overlap * (1.0 / ratio - 1.0))


def trapped_charge_split(ivc_volume_m3: float,
                         clearance_volume_m3: float,
                         intake_pressure_Pa: float,
                         intake_temperature_K: float,
                         exhaust_pressure_Pa: float,
                         exhaust_temperature_K: float,
                         valve_overlap_deg: float,
                         volumetric_efficiency: float = 1.0,
                         gas_constant_J_per_kg_K: float = _R_AIR) -> dict[str, float]:
    """Split the charge trapped at IVC into fresh mixture and hot residual.

    The residual mass is fixed by the clearance volume and the exhaust state, so
    it does not depend on how much fresh charge arrives. That makes the mixing
    close in one step rather than needing iteration: writing the ideal-gas
    relation at IVC for the *mixture* and the mixing relation for its
    temperature and eliminating ``T_mix`` gives::

        m_total = [ p_ivc * V_ivc / R  -  m_res * (T_res - T_intake) ] / T_intake

    from which the fresh mass and the residual fraction follow directly.
    """

    if ivc_volume_m3 <= 0.0:
        raise ValueError("ivc_volume_m3 must be positive.")
    if intake_temperature_K <= 0.0:
        raise ValueError("intake_temperature_K must be positive.")

    m_res = residual_gas_mass_kg(
        clearance_volume_m3=clearance_volume_m3,
        exhaust_pressure_Pa=exhaust_pressure_Pa,
        exhaust_temperature_K=exhaust_temperature_K,
        intake_pressure_Pa=intake_pressure_Pa,
        valve_overlap_deg=valve_overlap_deg,
        gas_constant_J_per_kg_K=gas_constant_J_per_kg_K,
    )

    p_ivc = volumetric_efficiency * intake_pressure_Pa
    capacity = p_ivc * ivc_volume_m3 / gas_constant_J_per_kg_K      # m * T at IVC
    m_total = (capacity - m_res * (exhaust_temperature_K - intake_temperature_K)) \
        / intake_temperature_K

    # A residual hot enough to dominate the cylinder would drive the total
    # negative; clamp it to something the solver can still march.
    if m_total <= 0.0 or m_res / m_total > _MAX_RESIDUAL_FRACTION:
        m_total = capacity / (
            _MAX_RESIDUAL_FRACTION * exhaust_temperature_K
            + (1.0 - _MAX_RESIDUAL_FRACTION) * intake_temperature_K
        )
        m_res = _MAX_RESIDUAL_FRACTION * m_total

    m_fresh = m_total - m_res
    fraction = m_res / m_total
    mixed_T = fraction * exhaust_temperature_K + (1.0 - fraction) * intake_temperature_K
    return {
        "total_mass_kg": m_total,
        "fresh_mass_kg": m_fresh,
        "residual_mass_kg": m_res,
        "residual_fraction": fraction,
        "mixed_temperature_K": mixed_T,
    }


# ------------------------------------------------------------------ summary

def breathing_report(geom: CylinderGeometry,
                     timing: ValveTiming,
                     valves: ValveGeometry,
                     mean_piston_speed_m_s: float,
                     intake_temperature_K: float,
                     ambient_pressure_Pa: float,
                     gamma: float = _GAMMA_AIR,
                     gas_constant_J_per_kg_K: float = _R_AIR) -> dict[str, Any]:
    """Everything the cycle solver and the console need from the valvetrain."""

    piston_area = geom.bore_area_m2
    a_in = valves.intake_flow_area_m2(geom.bore_m)
    a_ex = valves.exhaust_flow_area_m2(geom.bore_m)

    c_in = speed_of_sound_m_s(intake_temperature_K, gamma, gas_constant_J_per_kg_K)
    c_ex = speed_of_sound_m_s(_EXHAUST_TEMPERATURE_K, gamma, gas_constant_J_per_kg_K)

    z_in = mach_index(piston_area, mean_piston_speed_m_s, a_in, c_in)
    z_ex = mach_index(piston_area, mean_piston_speed_m_s, a_ex, c_ex)

    ve = volumetric_efficiency_from_mach_index(z_in)
    p_exhaust = exhaust_back_pressure_Pa(
        ambient_pressure_Pa, z_ex, valves.exhaust_restriction,
    )

    r_eff = effective_compression_ratio(geom, timing.ivc_theta_deg)
    r_exp = effective_expansion_ratio(geom, timing.evo_theta_deg)

    return {
        "intake_flow_area_m2": a_in,
        "exhaust_flow_area_m2": a_ex,
        "inlet_mach_index": z_in,
        "exhaust_mach_index": z_ex,
        "volumetric_efficiency": ve,
        "exhaust_pressure_Pa": p_exhaust,
        "effective_compression_ratio": r_eff,
        "effective_expansion_ratio": r_exp,
        "geometric_compression_ratio": geom.compression_ratio,
        "valve_overlap_deg": timing.valve_overlap_deg,
        "ivc_theta_deg": timing.ivc_theta_deg,
        "evo_theta_deg": timing.evo_theta_deg,
        "closed_period_deg": timing.closed_period_deg,
        "breathing_verdict": _breathing_verdict(z_in, ve, r_eff, geom.compression_ratio),
    }


def _breathing_verdict(z_in: float, ve: float, r_eff: float, r_geom: float) -> str:
    """One honest sentence about how this head and cam are behaving."""

    if z_in < _Z_KNEE * 0.6:
        breathing = "The inlet is nowhere near its limit at this speed."
    elif z_in < _Z_KNEE:
        breathing = "The inlet is approaching its flow limit."
    elif ve > 0.85:
        breathing = "The inlet is past its knee and starting to choke."
    else:
        breathing = "The inlet is choking badly; the valves are the limit here."

    # Every cam closes the intake somewhat after BDC, so a small gap is normal
    # and not worth remarking on. Only call it out once the cam is genuinely
    # trading compression for expansion.
    miller = ""
    if r_eff < r_geom - 1.5:
        miller = (
            f" Late intake closing drops the effective compression ratio to "
            f"{r_eff:.1f}:1 against a geometric {r_geom:.1f}:1."
        )
    return breathing + miller

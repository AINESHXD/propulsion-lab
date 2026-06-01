//! Turbojet cycle orchestration (Days 65-67).
//!
//! Chains the ported components — ISA atmosphere, freestream/inlet, compressor,
//! combustor, turbine, a convergent nozzle and the performance bookkeeping —
//! into a full dry-turbojet cycle, mirroring `app/engine_core/turbojet.py` for
//! the default (no afterburner / no bleed / constant-cp) path. Cycle-level
//! parity with Python is within 1e-6.

use wasm_bindgen::prelude::*;

use crate::components::{combustor_exit_native, compressor_exit_native, turbine_exit_native};
use crate::constants::*;
use crate::isa_atmosphere_native;

/// Headline turbojet cycle results (mirror of the Python result dict's core
/// fields). Station detail kept minimal here; the full station table stays on
/// the Python side.
#[wasm_bindgen]
#[derive(Clone, Copy, Debug)]
pub struct TurbojetOut {
    pub thrust_n: f64,
    pub thrust_kn: f64,
    pub specific_thrust_n_per_kg_s: f64,
    pub fuel_air_ratio: f64,
    pub fuel_flow_kg_s: f64,
    pub tsfc_kg_per_n_s: f64,
    pub tsfc_kg_per_kn_hr: f64,
    pub momentum_thrust_n: f64,
    pub pressure_thrust_n: f64,
    pub exit_velocity_m_s: f64,
    pub nozzle_exit_pressure_pa: f64,
    pub nozzle_choked: bool,
    pub tt5_k: f64,
    pub pt5_pa: f64,
    pub freestream_velocity_m_s: f64,
    pub thermal_efficiency_estimate: f64,
    pub propulsive_efficiency_estimate: f64,
    pub overall_efficiency_estimate: f64,
}

#[allow(clippy::too_many_arguments)]
pub fn turbojet_cycle_native(
    altitude_m: f64,
    mach: f64,
    mass_flow_air_kg_s: f64,
    compressor_pressure_ratio: f64,
    compressor_efficiency: f64,
    turbine_inlet_temperature_k: f64,
    turbine_efficiency: f64,
    combustor_efficiency: f64,
    combustor_pressure_loss_fraction: f64,
    mechanical_efficiency: f64,
    nozzle_efficiency: f64,
    inlet_pressure_recovery: f64,
    fuel_heating_value_j_kg: f64,
) -> Result<TurbojetOut, String> {
    if mach < 0.0 {
        return Err("Mach number must be non-negative.".into());
    }
    if mass_flow_air_kg_s <= 0.0 {
        return Err("Air mass flow must be positive.".into());
    }
    if !(inlet_pressure_recovery > 0.0 && inlet_pressure_recovery <= 1.0) {
        return Err("Inlet pressure recovery must be between 0 and 1.".into());
    }
    if !(nozzle_efficiency > 0.0 && nozzle_efficiency <= 1.0) {
        return Err("Nozzle efficiency must be between 0 and 1.".into());
    }

    // --- Freestream + inlet -------------------------------------------------
    let atm = isa_atmosphere_native(altitude_m);
    let v0 = mach * atm.speed_of_sound_m_s;
    let ram = 1.0 + 0.5 * (GAMMA_AIR - 1.0) * mach * mach;
    let tt0 = atm.temperature_k * ram;
    let pt0 = atm.pressure_pa * ram.powf(GAMMA_AIR / (GAMMA_AIR - 1.0));
    let tt2 = tt0;
    let pt2 = pt0 * inlet_pressure_recovery;

    // --- Core components ----------------------------------------------------
    let comp = compressor_exit_native(tt2, pt2, compressor_pressure_ratio, compressor_efficiency)?;
    let comb = combustor_exit_native(
        comp.tt3_k,
        comp.pt3_pa,
        turbine_inlet_temperature_k,
        combustor_efficiency,
        combustor_pressure_loss_fraction,
        fuel_heating_value_j_kg,
    )?;
    let far = comb.fuel_air_ratio;
    let turb = turbine_exit_native(
        turbine_inlet_temperature_k,
        comb.pt4_pa,
        comp.specific_work_j_kg,
        far,
        mechanical_efficiency,
        turbine_efficiency,
        None,
    )?;
    let tt5 = turb.tt5_k;
    let pt5 = turb.pt5_pa;

    if pt5 <= atm.pressure_pa {
        return Err("Turbine exit stagnation pressure is at or below ambient.".into());
    }

    // --- Convergent nozzle (no specified area; continuity exit area) --------
    let critical_pressure = pt5 * (2.0 / (GAMMA_GAS + 1.0)).powf(GAMMA_GAS / (GAMMA_GAS - 1.0));
    let choked = critical_pressure > atm.pressure_pa;
    let (exit_pressure, exit_velocity);
    if choked {
        exit_pressure = critical_pressure;
        let t_ideal = tt5 * 2.0 / (GAMMA_GAS + 1.0);
        let v_ideal = (GAMMA_GAS * R_AIR * t_ideal).sqrt();
        exit_velocity = nozzle_efficiency.sqrt() * v_ideal;
    } else {
        exit_pressure = atm.pressure_pa;
        let t_isentropic = tt5 * (exit_pressure / pt5).powf((GAMMA_GAS - 1.0) / GAMMA_GAS);
        let drop = tt5 - t_isentropic;
        if drop <= 0.0 {
            return Err("Nozzle has no positive temperature drop available.".into());
        }
        exit_velocity = (2.0 * nozzle_efficiency * CP_GAS * drop).sqrt();
    }
    let exit_static_temp = tt5 - exit_velocity * exit_velocity / (2.0 * CP_GAS);
    if exit_static_temp <= 0.0 || exit_velocity <= 0.0 {
        return Err("Nozzle exit state is non-physical.".into());
    }
    let exit_density = exit_pressure / (R_AIR * exit_static_temp);
    let total_mass_flow = mass_flow_air_kg_s * (1.0 + far);
    let estimated_exit_area = total_mass_flow / (exit_density * exit_velocity);
    let pressure_thrust = (exit_pressure - atm.pressure_pa) * estimated_exit_area;

    // --- Performance --------------------------------------------------------
    let fuel_flow = far * mass_flow_air_kg_s;
    let exit_mass_flow = mass_flow_air_kg_s * (1.0 + far);
    let momentum_thrust = exit_mass_flow * exit_velocity - mass_flow_air_kg_s * v0;
    let thrust = momentum_thrust + pressure_thrust;
    if thrust <= 0.0 {
        return Err("Cycle produced non-positive net thrust.".into());
    }
    let tsfc_n_s = fuel_flow / thrust;
    let jet_ke = 0.5 * (exit_mass_flow * exit_velocity * exit_velocity
        - mass_flow_air_kg_s * v0 * v0);
    let pressure_power = pressure_thrust * v0;
    let jet_available = jet_ke + pressure_power;
    let fuel_power = fuel_flow * fuel_heating_value_j_kg;
    let propulsive_power = thrust * v0;

    let thermal = if fuel_power > 0.0 && jet_available > 0.0 {
        jet_available / fuel_power
    } else {
        0.0
    };
    let propulsive = if v0 == 0.0 || jet_available <= 0.0 {
        0.0
    } else {
        propulsive_power / jet_available
    };
    let overall = if fuel_power > 0.0 {
        propulsive_power / fuel_power
    } else {
        0.0
    };

    Ok(TurbojetOut {
        thrust_n: thrust,
        thrust_kn: thrust / 1000.0,
        specific_thrust_n_per_kg_s: thrust / mass_flow_air_kg_s,
        fuel_air_ratio: far,
        fuel_flow_kg_s: fuel_flow,
        tsfc_kg_per_n_s: tsfc_n_s,
        tsfc_kg_per_kn_hr: tsfc_n_s * 1000.0 * 3600.0,
        momentum_thrust_n: momentum_thrust,
        pressure_thrust_n: pressure_thrust,
        exit_velocity_m_s: exit_velocity,
        nozzle_exit_pressure_pa: exit_pressure,
        nozzle_choked: choked,
        tt5_k: tt5,
        pt5_pa: pt5,
        freestream_velocity_m_s: v0,
        thermal_efficiency_estimate: thermal,
        propulsive_efficiency_estimate: propulsive,
        overall_efficiency_estimate: overall,
    })
}

/// WASM/JS entry point for the full dry turbojet cycle.
#[wasm_bindgen]
#[allow(clippy::too_many_arguments)]
pub fn turbojet_cycle(
    altitude_m: f64,
    mach: f64,
    mass_flow_air_kg_s: f64,
    compressor_pressure_ratio: f64,
    compressor_efficiency: f64,
    turbine_inlet_temperature_k: f64,
    turbine_efficiency: f64,
    combustor_efficiency: f64,
    combustor_pressure_loss_fraction: f64,
    mechanical_efficiency: f64,
    nozzle_efficiency: f64,
    inlet_pressure_recovery: f64,
    fuel_heating_value_j_kg: f64,
) -> Result<TurbojetOut, JsValue> {
    turbojet_cycle_native(
        altitude_m,
        mach,
        mass_flow_air_kg_s,
        compressor_pressure_ratio,
        compressor_efficiency,
        turbine_inlet_temperature_k,
        turbine_efficiency,
        combustor_efficiency,
        combustor_pressure_loss_fraction,
        mechanical_efficiency,
        nozzle_efficiency,
        inlet_pressure_recovery,
        fuel_heating_value_j_kg,
    )
    .map_err(|e| JsValue::from_str(&e))
}

// ===========================================================================
// Turbofan (separate-flow, dry) — mirror of simulate_turbofan_cycle
// ===========================================================================

/// One convergent-nozzle stream result (mirror of the convergent path of
/// `expand_nozzle_stream`). `gas_constant` is R_air for both streams, as in the
/// Python code.
struct StreamResult {
    exit_velocity_m_s: f64,
    exit_pressure_pa: f64,
    choked: bool,
    momentum_thrust_n: f64,
    pressure_thrust_n: f64,
}

#[allow(clippy::too_many_arguments)]
fn convergent_stream(
    tt_k: f64,
    pt_pa: f64,
    ambient_pa: f64,
    mass_in_kg_s: f64,
    fuel_air_ratio: f64,
    v0_m_s: f64,
    nozzle_efficiency: f64,
    gamma: f64,
    cp: f64,
    name: &str,
) -> Result<StreamResult, String> {
    if pt_pa <= ambient_pa {
        return Err(format!("{name}: inlet stagnation pressure must exceed ambient."));
    }
    let critical = pt_pa * (2.0 / (gamma + 1.0)).powf(gamma / (gamma - 1.0));
    let choked = critical > ambient_pa;
    let exit_pressure;
    let exit_velocity;
    if choked {
        exit_pressure = critical;
        let t_ideal = tt_k * 2.0 / (gamma + 1.0);
        let v_ideal = (gamma * R_AIR * t_ideal).sqrt();
        exit_velocity = nozzle_efficiency.sqrt() * v_ideal;
    } else {
        exit_pressure = ambient_pa;
        let t_isentropic = tt_k * (exit_pressure / pt_pa).powf((gamma - 1.0) / gamma);
        let drop = tt_k - t_isentropic;
        if drop <= 0.0 {
            return Err(format!("{name}: no positive temperature drop available."));
        }
        exit_velocity = (2.0 * nozzle_efficiency * cp * drop).sqrt();
    }
    let exit_static_temp = tt_k - exit_velocity * exit_velocity / (2.0 * cp);
    if exit_static_temp <= 0.0 || exit_velocity <= 0.0 {
        return Err(format!("{name}: exit state is non-physical."));
    }
    let mass_out = mass_in_kg_s * (1.0 + fuel_air_ratio);
    let exit_density = exit_pressure / (R_AIR * exit_static_temp);
    let exit_area = mass_out / (exit_density * exit_velocity);
    let pressure_thrust = (exit_pressure - ambient_pa) * exit_area;
    let momentum_thrust = mass_out * exit_velocity - mass_in_kg_s * v0_m_s;
    Ok(StreamResult {
        exit_velocity_m_s: exit_velocity,
        exit_pressure_pa: exit_pressure,
        choked,
        momentum_thrust_n: momentum_thrust,
        pressure_thrust_n: pressure_thrust,
    })
}

/// Headline separate-flow turbofan results (mirror of the Python result dict).
#[wasm_bindgen]
#[derive(Clone, Copy, Debug)]
pub struct TurbofanOut {
    pub thrust_n: f64,
    pub thrust_kn: f64,
    pub core_thrust_n: f64,
    pub bypass_thrust_n: f64,
    pub specific_thrust_n_per_kg_s: f64,
    pub fuel_air_ratio: f64,
    pub fuel_flow_kg_s: f64,
    pub tsfc_kg_per_kn_hr: f64,
    pub exit_velocity_m_s: f64,
    pub bypass_exit_velocity_m_s: f64,
    pub momentum_thrust_n: f64,
    pub pressure_thrust_n: f64,
    pub nozzle_choked: bool,
    pub bypass_nozzle_choked: bool,
    pub tt5_k: f64,
    pub pt5_pa: f64,
    pub thermal_efficiency_estimate: f64,
    pub propulsive_efficiency_estimate: f64,
    pub overall_efficiency_estimate: f64,
}

#[allow(clippy::too_many_arguments)]
pub fn turbofan_cycle_native(
    altitude_m: f64,
    mach: f64,
    total_mass_flow_air_kg_s: f64,
    bypass_ratio: f64,
    fan_pressure_ratio: f64,
    fan_efficiency: f64,
    core_compressor_pressure_ratio: f64,
    compressor_efficiency: f64,
    turbine_inlet_temperature_k: f64,
    hp_turbine_efficiency: f64,
    lp_turbine_efficiency: f64,
    combustor_efficiency: f64,
    combustor_pressure_loss_fraction: f64,
    mechanical_efficiency: f64,
    core_nozzle_efficiency: f64,
    bypass_nozzle_efficiency: f64,
    inlet_pressure_recovery: f64,
    fuel_heating_value_j_kg: f64,
) -> Result<TurbofanOut, String> {
    if mach < 0.0 {
        return Err("Mach number must be non-negative.".into());
    }
    if total_mass_flow_air_kg_s <= 0.0 {
        return Err("Total air mass flow must be positive.".into());
    }
    if bypass_ratio < 0.0 {
        return Err("Bypass ratio must be non-negative.".into());
    }
    if fan_pressure_ratio <= 1.0 {
        return Err("Fan pressure ratio must exceed 1.".into());
    }
    if !(fan_efficiency > 0.0 && fan_efficiency <= 1.0) {
        return Err("Fan efficiency must be between 0 and 1.".into());
    }

    let atm = isa_atmosphere_native(altitude_m);
    let v0 = mach * atm.speed_of_sound_m_s;
    let ram = 1.0 + 0.5 * (GAMMA_AIR - 1.0) * mach * mach;
    let tt2 = atm.temperature_k * ram;
    let pt2 = atm.pressure_pa * ram.powf(GAMMA_AIR / (GAMMA_AIR - 1.0)) * inlet_pressure_recovery;

    let core_mass = total_mass_flow_air_kg_s / (1.0 + bypass_ratio);
    let bypass_mass = total_mass_flow_air_kg_s - core_mass;

    // Fan (station 13).
    let tt13s = tt2 * fan_pressure_ratio.powf((GAMMA_AIR - 1.0) / GAMMA_AIR);
    let tt13 = tt2 + (tt13s - tt2) / fan_efficiency;
    let pt13 = pt2 * fan_pressure_ratio;
    let fan_work = CP_AIR * (tt13 - tt2);

    // Core: HPC, combustor.
    let hpc = compressor_exit_native(tt13, pt13, core_compressor_pressure_ratio, compressor_efficiency)?;
    let comb = combustor_exit_native(
        hpc.tt3_k,
        hpc.pt3_pa,
        turbine_inlet_temperature_k,
        combustor_efficiency,
        combustor_pressure_loss_fraction,
        fuel_heating_value_j_kg,
    )?;
    let far = comb.fuel_air_ratio;
    let pt4 = comb.pt4_pa;
    let mass_ratio = 1.0 + far;

    // Two-spool work split: HPT drives HPC, LPT drives fan (over all fan flow).
    let fan_work_per_core = fan_work * (1.0 + bypass_ratio);
    let tt4 = turbine_inlet_temperature_k;
    let drop_hpt = hpc.specific_work_j_kg / (mass_ratio * CP_GAS * mechanical_efficiency);
    let tt45 = tt4 - drop_hpt;
    if tt45 <= 0.0 {
        return Err("HPT work extraction produced non-positive T45.".into());
    }
    let tt45s = tt4 - drop_hpt / hp_turbine_efficiency;
    let pt45 = pt4 * (tt45s / tt4).powf(GAMMA_GAS / (GAMMA_GAS - 1.0));
    let drop_lpt = fan_work_per_core / (mass_ratio * CP_GAS * mechanical_efficiency);
    let tt5 = tt45 - drop_lpt;
    if tt5 <= 0.0 {
        return Err("LPT work extraction produced non-positive T5.".into());
    }
    let tt5s = tt45 - drop_lpt / lp_turbine_efficiency;
    let pt5 = pt45 * (tt5s / tt45).powf(GAMMA_GAS / (GAMMA_GAS - 1.0));

    // Separate-flow exhaust: core (hot gas) + bypass (air).
    let core = convergent_stream(
        tt5, pt5, atm.pressure_pa, core_mass, far, v0, core_nozzle_efficiency,
        GAMMA_GAS, CP_GAS, "Core nozzle",
    )?;
    let bypass = convergent_stream(
        tt13, pt13, atm.pressure_pa, bypass_mass, 0.0, v0, bypass_nozzle_efficiency,
        GAMMA_AIR, CP_AIR, "Bypass nozzle",
    )?;

    let momentum_thrust = core.momentum_thrust_n + bypass.momentum_thrust_n;
    let pressure_thrust = core.pressure_thrust_n + bypass.pressure_thrust_n;
    let thrust = momentum_thrust + pressure_thrust;
    if thrust <= 0.0 {
        return Err("Turbofan cycle produced non-positive net thrust.".into());
    }
    let core_thrust = core.momentum_thrust_n + core.pressure_thrust_n;
    let bypass_thrust = bypass.momentum_thrust_n + bypass.pressure_thrust_n;

    let fuel_flow = far * core_mass;
    let tsfc_n_s = fuel_flow / thrust;

    let jet_ke = 0.5
        * (core_mass * (1.0 + far) * core.exit_velocity_m_s * core.exit_velocity_m_s
            + bypass_mass * bypass.exit_velocity_m_s * bypass.exit_velocity_m_s
            - total_mass_flow_air_kg_s * v0 * v0);
    let pressure_power = pressure_thrust * v0;
    let useful_jet_power = jet_ke + pressure_power;
    let fuel_power = fuel_flow * fuel_heating_value_j_kg;
    let propulsive_power = thrust * v0;

    let clamp01 = |x: f64| x.max(0.0).min(1.0);
    let thermal = clamp01(if fuel_power > 0.0 && useful_jet_power > 0.0 {
        useful_jet_power / fuel_power
    } else {
        0.0
    });
    let propulsive = clamp01(if useful_jet_power > 0.0 {
        propulsive_power / useful_jet_power
    } else {
        0.0
    });
    let overall = clamp01(if fuel_power > 0.0 {
        propulsive_power / fuel_power
    } else {
        0.0
    });

    Ok(TurbofanOut {
        thrust_n: thrust,
        thrust_kn: thrust / 1000.0,
        core_thrust_n: core_thrust,
        bypass_thrust_n: bypass_thrust,
        specific_thrust_n_per_kg_s: thrust / total_mass_flow_air_kg_s,
        fuel_air_ratio: far,
        fuel_flow_kg_s: fuel_flow,
        tsfc_kg_per_kn_hr: tsfc_n_s * 1000.0 * 3600.0,
        exit_velocity_m_s: core.exit_velocity_m_s,
        bypass_exit_velocity_m_s: bypass.exit_velocity_m_s,
        momentum_thrust_n: momentum_thrust,
        pressure_thrust_n: pressure_thrust,
        nozzle_choked: core.choked,
        bypass_nozzle_choked: bypass.choked,
        tt5_k: tt5,
        pt5_pa: pt5,
        thermal_efficiency_estimate: thermal,
        propulsive_efficiency_estimate: propulsive,
        overall_efficiency_estimate: overall,
    })
}

/// WASM/JS entry point for the separate-flow dry turbofan cycle.
#[wasm_bindgen]
#[allow(clippy::too_many_arguments)]
pub fn turbofan_cycle(
    altitude_m: f64,
    mach: f64,
    total_mass_flow_air_kg_s: f64,
    bypass_ratio: f64,
    fan_pressure_ratio: f64,
    fan_efficiency: f64,
    core_compressor_pressure_ratio: f64,
    compressor_efficiency: f64,
    turbine_inlet_temperature_k: f64,
    hp_turbine_efficiency: f64,
    lp_turbine_efficiency: f64,
    combustor_efficiency: f64,
    combustor_pressure_loss_fraction: f64,
    mechanical_efficiency: f64,
    core_nozzle_efficiency: f64,
    bypass_nozzle_efficiency: f64,
    inlet_pressure_recovery: f64,
    fuel_heating_value_j_kg: f64,
) -> Result<TurbofanOut, JsValue> {
    turbofan_cycle_native(
        altitude_m,
        mach,
        total_mass_flow_air_kg_s,
        bypass_ratio,
        fan_pressure_ratio,
        fan_efficiency,
        core_compressor_pressure_ratio,
        compressor_efficiency,
        turbine_inlet_temperature_k,
        hp_turbine_efficiency,
        lp_turbine_efficiency,
        combustor_efficiency,
        combustor_pressure_loss_fraction,
        mechanical_efficiency,
        core_nozzle_efficiency,
        bypass_nozzle_efficiency,
        inlet_pressure_recovery,
        fuel_heating_value_j_kg,
    )
    .map_err(|e| JsValue::from_str(&e))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rel(a: f64, b: f64) -> f64 {
        (a - b).abs() / b.abs().max(1e-300)
    }

    /// Default deck cycle vs Python `simulate_turbojet_cycle(TurbojetCycleInputs())`.
    #[test]
    fn default_turbojet_cycle_matches_python() {
        let r = turbojet_cycle_native(
            10000.0, 0.8, 50.0, 12.0, 0.86, 1400.0, 0.88, 0.99, 0.05, 0.99, 0.95, 0.98, 43e6,
        )
        .unwrap();
        assert!(rel(r.thrust_n, 36040.16868643273) < 1e-6);
        assert!(rel(r.thrust_kn, 36.04016868643273) < 1e-6);
        assert!(rel(r.specific_thrust_n_per_kg_s, 720.8033737286546) < 1e-6);
        assert!(rel(r.fuel_air_ratio, 0.025718912918016368) < 1e-6);
        assert!(rel(r.fuel_flow_kg_s, 1.2859456459008185) < 1e-6);
        assert!(rel(r.tsfc_kg_per_n_s, 3.568089975075258e-05) < 1e-6);
        assert!(rel(r.tsfc_kg_per_kn_hr, 128.45123910270928) < 1e-6);
        assert!(rel(r.momentum_thrust_n, 18570.529319524787) < 1e-6);
        assert!(rel(r.pressure_thrust_n, 17469.63936690794) < 1e-6);
        assert!(rel(r.exit_velocity_m_s, 595.6398456517172) < 1e-6);
        assert!(rel(r.nozzle_exit_pressure_pa, 93491.02868322065) < 1e-6);
        assert!(rel(r.tt5_k, 1139.8199845104832) < 1e-6);
        assert!(rel(r.pt5_pa, 173014.90408676097) < 1e-6);
        assert!(rel(r.freestream_velocity_m_s, 239.54846858203874) < 1e-6);
        assert!(rel(r.thermal_efficiency_estimate, 0.21426685155377068) < 1e-6);
        assert!(rel(r.propulsive_efficiency_estimate, 0.7286754835244832) < 1e-6);
        assert!(rel(r.overall_efficiency_estimate, 0.1561310016592125) < 1e-6);
        assert!(r.nozzle_choked);
    }

    /// Default deck cycle vs Python `simulate_turbofan_cycle(TurbofanCycleInputs())`.
    #[test]
    fn default_turbofan_cycle_matches_python() {
        let r = turbofan_cycle_native(
            10000.0, 0.78, 220.0, 5.0, 1.55, 0.89, 18.0, 0.88, 1550.0, 0.9, 0.9, 0.99, 0.05,
            0.99, 0.95, 0.94, 0.98, 43e6,
        )
        .unwrap();
        assert!(rel(r.thrust_n, 42564.79256354629) < 1e-6);
        assert!(rel(r.thrust_kn, 42.56479256354629) < 1e-6);
        assert!(rel(r.core_thrust_n, 23150.560864858984) < 1e-6);
        assert!(rel(r.bypass_thrust_n, 19414.231698687305) < 1e-6);
        assert!(rel(r.specific_thrust_n_per_kg_s, 193.4763298343013) < 1e-6);
        assert!(rel(r.fuel_air_ratio, 0.026282038052179622) < 1e-6);
        assert!(rel(r.fuel_flow_kg_s, 0.9636747285799194) < 1e-6);
        assert!(rel(r.tsfc_kg_per_kn_hr, 81.50466180960217) < 1e-6);
        assert!(rel(r.exit_velocity_m_s, 556.7379302916315) < 1e-6);
        assert!(rel(r.bypass_exit_velocity_m_s, 300.97983433264733) < 1e-6);
        assert!(rel(r.momentum_thrust_n, 24746.728168028454) < 1e-6);
        assert!(rel(r.pressure_thrust_n, 17818.06439551784) < 1e-6);
        assert!(rel(r.tt5_k, 995.7960599038461) < 1e-6);
        assert!(rel(r.pt5_pa, 137565.91403745307) < 1e-6);
        assert!(rel(r.thermal_efficiency_estimate, 0.296755063068299) < 1e-6);
        assert!(rel(r.propulsive_efficiency_estimate, 0.8084468488085301) < 1e-6);
        assert!(rel(r.overall_efficiency_estimate, 0.23991069560554296) < 1e-6);
        assert!(r.nozzle_choked && r.bypass_nozzle_choked);
    }
}

//! Compressor, combustor and turbine station calculations (Day 63-64).
//!
//! Direct ports of `app/engine_core/{compressor,combustor,turbine}.py`. Each
//! `*_native` function is the pure, host-testable core (validated, returning a
//! `Result`); the `#[wasm_bindgen]` wrapper maps the error to a JS exception.
//! Constants come from `crate::constants`, identical to the Python `constants`
//! module, so the Rust and Python results agree to within 1e-9.

use wasm_bindgen::prelude::*;

use crate::constants::*;

// ---------------------------------------------------------------------------
// Compressor (station 3)
// ---------------------------------------------------------------------------

#[wasm_bindgen]
#[derive(Clone, Copy, Debug)]
pub struct CompressorOut {
    pub tt3_k: f64,
    pub pt3_pa: f64,
    pub specific_work_j_kg: f64,
    pub tt3s_k: f64,
}

/// Adiabatic compressor exit from inlet stagnation state, pressure ratio and
/// isentropic efficiency. Mirror of `calculate_compressor_exit`.
pub fn compressor_exit_native(
    tt2_k: f64,
    pt2_pa: f64,
    pressure_ratio: f64,
    efficiency: f64,
) -> Result<CompressorOut, String> {
    if pressure_ratio <= 1.0 {
        return Err("Compressor pressure ratio must exceed 1.".into());
    }
    if !(efficiency > 0.0 && efficiency <= 1.0) {
        return Err("Compressor efficiency must be between 0 and 1.".into());
    }
    let tr_isentropic = pressure_ratio.powf((GAMMA_AIR - 1.0) / GAMMA_AIR);
    let tt3s = tt2_k * tr_isentropic;
    let tt3 = tt2_k + (tt3s - tt2_k) / efficiency;
    let pt3 = pt2_pa * pressure_ratio;
    let work = CP_AIR * (tt3 - tt2_k);
    Ok(CompressorOut {
        tt3_k: tt3,
        pt3_pa: pt3,
        specific_work_j_kg: work,
        tt3s_k: tt3s,
    })
}

#[wasm_bindgen]
pub fn compressor_exit(
    tt2_k: f64,
    pt2_pa: f64,
    pressure_ratio: f64,
    efficiency: f64,
) -> Result<CompressorOut, JsValue> {
    compressor_exit_native(tt2_k, pt2_pa, pressure_ratio, efficiency)
        .map_err(|e| JsValue::from_str(&e))
}

// ---------------------------------------------------------------------------
// Combustor (station 4)
// ---------------------------------------------------------------------------

#[wasm_bindgen]
#[derive(Clone, Copy, Debug)]
pub struct CombustorOut {
    pub fuel_air_ratio: f64,
    pub pt4_pa: f64,
}

/// Combustor exit fuel-air ratio and stagnation pressure from a constant-cp
/// energy balance. Mirror of `calculate_combustor_exit`.
pub fn combustor_exit_native(
    tt3_k: f64,
    pt3_pa: f64,
    turbine_inlet_temperature_k: f64,
    combustor_efficiency: f64,
    pressure_loss_fraction: f64,
    fuel_heating_value_j_kg: f64,
) -> Result<CombustorOut, String> {
    if !(combustor_efficiency > 0.0 && combustor_efficiency <= 1.0) {
        return Err("Combustor efficiency must be between 0 and 1.".into());
    }
    if !(0.0..=0.3).contains(&pressure_loss_fraction) {
        return Err("Combustor pressure loss fraction must be 0 to 0.3.".into());
    }
    if fuel_heating_value_j_kg <= 1e6 {
        return Err("Fuel heating value must exceed 1e6 J/kg.".into());
    }
    if turbine_inlet_temperature_k <= tt3_k {
        return Err("Turbine inlet temperature must exceed compressor exit temperature.".into());
    }
    let numerator = CP_GAS * turbine_inlet_temperature_k - CP_AIR * tt3_k;
    let denominator = combustor_efficiency * fuel_heating_value_j_kg
        - CP_GAS * turbine_inlet_temperature_k;
    if denominator <= 0.0 {
        return Err("Combustor energy balance is impossible because fuel heat release is too low.".into());
    }
    let fuel_air_ratio = numerator / denominator;
    if fuel_air_ratio <= 0.0 {
        return Err("Combustor produced a non-positive fuel-air ratio.".into());
    }
    let pt4 = pt3_pa * (1.0 - pressure_loss_fraction);
    if pt4 <= 0.0 {
        return Err("Combustor pressure loss produced non-positive pressure.".into());
    }
    Ok(CombustorOut {
        fuel_air_ratio,
        pt4_pa: pt4,
    })
}

#[wasm_bindgen]
pub fn combustor_exit(
    tt3_k: f64,
    pt3_pa: f64,
    turbine_inlet_temperature_k: f64,
    combustor_efficiency: f64,
    pressure_loss_fraction: f64,
    fuel_heating_value_j_kg: f64,
) -> Result<CombustorOut, JsValue> {
    combustor_exit_native(
        tt3_k,
        pt3_pa,
        turbine_inlet_temperature_k,
        combustor_efficiency,
        pressure_loss_fraction,
        fuel_heating_value_j_kg,
    )
    .map_err(|e| JsValue::from_str(&e))
}

// ---------------------------------------------------------------------------
// Turbine (station 5)
// ---------------------------------------------------------------------------

#[wasm_bindgen]
#[derive(Clone, Copy, Debug)]
pub struct TurbineOut {
    pub tt5_k: f64,
    pub pt5_pa: f64,
    pub tt5s_k: f64,
}

/// Turbine exit from the compressor work balance and turbine efficiency. Mirror
/// of `calculate_turbine_exit`. `gas_mass_flow_ratio` (m_HPT / m_air) overrides
/// the `1 + fuel_air_ratio` denominator when provided (bleed / cooling air).
pub fn turbine_exit_native(
    tt4_k: f64,
    pt4_pa: f64,
    compressor_specific_work_j_kg: f64,
    fuel_air_ratio: f64,
    mechanical_efficiency: f64,
    turbine_efficiency: f64,
    gas_mass_flow_ratio: Option<f64>,
) -> Result<TurbineOut, String> {
    if compressor_specific_work_j_kg <= 0.0 {
        return Err("Compressor specific work must be positive.".into());
    }
    if fuel_air_ratio <= 0.0 {
        return Err("Fuel-air ratio must be positive.".into());
    }
    if !(mechanical_efficiency > 0.0 && mechanical_efficiency <= 1.0) {
        return Err("Mechanical efficiency must be between 0 and 1.".into());
    }
    if !(turbine_efficiency > 0.0 && turbine_efficiency <= 1.0) {
        return Err("Turbine efficiency must be between 0 and 1.".into());
    }
    let effective_mass_ratio = gas_mass_flow_ratio.unwrap_or(1.0 + fuel_air_ratio);
    if effective_mass_ratio <= 0.0 {
        return Err("Turbine gas mass flow ratio must be positive.".into());
    }
    let drop = compressor_specific_work_j_kg / (effective_mass_ratio * CP_GAS * mechanical_efficiency);
    let tt5 = tt4_k - drop;
    if tt5 <= 0.0 {
        return Err("Turbine work extraction produced non-positive T05.".into());
    }
    let tt5s = tt4_k - (tt4_k - tt5) / turbine_efficiency;
    if tt5s <= 0.0 {
        return Err("Turbine isentropic exit temperature is non-positive.".into());
    }
    let pressure_ratio = (tt5s / tt4_k).powf(GAMMA_GAS / (GAMMA_GAS - 1.0));
    let pt5 = pt4_pa * pressure_ratio;
    if pt5 <= 0.0 {
        return Err("Turbine exit pressure is non-positive.".into());
    }
    Ok(TurbineOut {
        tt5_k: tt5,
        pt5_pa: pt5,
        tt5s_k: tt5s,
    })
}

#[wasm_bindgen]
pub fn turbine_exit(
    tt4_k: f64,
    pt4_pa: f64,
    compressor_specific_work_j_kg: f64,
    fuel_air_ratio: f64,
    mechanical_efficiency: f64,
    turbine_efficiency: f64,
    gas_mass_flow_ratio: Option<f64>,
) -> Result<TurbineOut, JsValue> {
    turbine_exit_native(
        tt4_k,
        pt4_pa,
        compressor_specific_work_j_kg,
        fuel_air_ratio,
        mechanical_efficiency,
        turbine_efficiency,
        gas_mass_flow_ratio,
    )
    .map_err(|e| JsValue::from_str(&e))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rel(a: f64, b: f64) -> f64 {
        (a - b).abs() / b.abs().max(1e-300)
    }

    // Reference values: chained case Tt2=288.15 K, Pt2=101325 Pa, PR=12, eta_c=0.86,
    // TIT=1400 K, eta_b=0.99, loss=0.05, LHV=43e6, eta_m=0.99, eta_t=0.88.
    // Produced by the Python component functions.
    #[test]
    fn compressor_matches_python() {
        let c = compressor_exit_native(288.15, 101325.0, 12.0, 0.86).unwrap();
        assert!(rel(c.tt3_k, 634.5790108979829) < 1e-9);
        assert!(rel(c.pt3_pa, 1215900.0) < 1e-9);
        assert!(rel(c.specific_work_j_kg, 347814.7269415749) < 1e-9);
        assert!(rel(c.tt3s_k, 586.0789493722652) < 1e-9);
    }

    #[test]
    fn combustor_matches_python() {
        let b = combustor_exit_native(634.5790108979829, 1215900.0, 1400.0, 0.99, 0.05, 43e6).unwrap();
        assert!(rel(b.fuel_air_ratio, 0.02375201838521546) < 1e-9);
        assert!(rel(b.pt4_pa, 1155105.0) < 1e-9);
    }

    #[test]
    fn turbine_matches_python() {
        let t = turbine_exit_native(
            1400.0,
            1155105.0,
            347814.7269415749,
            0.02375201838521546,
            0.99,
            0.88,
            None,
        )
        .unwrap();
        assert!(rel(t.tt5_k, 1101.5853357977737) < 1e-9);
        assert!(rel(t.pt5_pa, 377697.8525758245) < 1e-9);
        assert!(rel(t.tt5s_k, 1060.8924270429247) < 1e-9);
    }

    #[test]
    fn invalid_inputs_error() {
        assert!(compressor_exit_native(288.15, 101325.0, 0.9, 0.86).is_err());
        assert!(combustor_exit_native(700.0, 1e6 * 2.0, 600.0, 0.99, 0.05, 43e6).is_err());
        assert!(turbine_exit_native(1400.0, 1e6, -1.0, 0.02, 0.99, 0.88, None).is_err());
    }
}

//! PropulsionLab cycle core, ported to Rust for a WebAssembly build.
//!
//! Day 61-62 scaffolds the crate and the build pipeline; this first module ports
//! the ISA atmosphere so there is a real computation behind a `wasm_bindgen`
//! export and a native parity test against the Python reference. Subsequent days
//! port the compressor, turbine and combustor, then the cycle orchestration.
//!
//! Every constant mirrors `app/engine_core/constants.py` exactly so the Rust and
//! Python results agree to within 1e-9 (the parity gate in the plan).

use wasm_bindgen::prelude::*;

pub mod components;
pub mod cycle;

/// Perfect-gas constants — kept byte-identical to the Python `constants` module.
pub mod constants {
    pub const GAMMA_AIR: f64 = 1.4;
    pub const CP_AIR: f64 = 1004.0;
    pub const R_AIR: f64 = 287.0;
    pub const GAMMA_GAS: f64 = 1.33;
    pub const CP_GAS: f64 = 1150.0;
    pub const G0: f64 = 9.80665;
    pub const T_SL: f64 = 288.15;
    pub const P_SL: f64 = 101325.0;
    pub const L_LAPSE: f64 = 0.0065;
}

/// Static ambient atmosphere state (mirror of the Python `AtmosphereState`).
#[wasm_bindgen]
#[derive(Clone, Copy, Debug)]
pub struct Atmosphere {
    pub temperature_k: f64,
    pub pressure_pa: f64,
    pub density_kg_m3: f64,
    pub speed_of_sound_m_s: f64,
}

/// Pure, host-testable ISA atmosphere from sea level to ~25 km.
///
/// Troposphere model through 11 km; isothermal lower stratosphere at 216.65 K
/// above it. Identical formulation to `app/engine_core/atmosphere.py`.
pub fn isa_atmosphere_native(altitude_m: f64) -> Atmosphere {
    use constants::*;
    let temperature_k;
    let pressure_pa;
    if altitude_m <= 11000.0 {
        temperature_k = T_SL - L_LAPSE * altitude_m;
        pressure_pa = P_SL * (temperature_k / T_SL).powf(G0 / (R_AIR * L_LAPSE));
    } else {
        let tropopause_t = T_SL - L_LAPSE * 11000.0;
        let tropopause_p = P_SL * (tropopause_t / T_SL).powf(G0 / (R_AIR * L_LAPSE));
        temperature_k = tropopause_t;
        pressure_pa =
            tropopause_p * (-G0 * (altitude_m - 11000.0) / (R_AIR * tropopause_t)).exp();
    }
    let density_kg_m3 = pressure_pa / (R_AIR * temperature_k);
    let speed_of_sound_m_s = (GAMMA_AIR * R_AIR * temperature_k).sqrt();
    Atmosphere {
        temperature_k,
        pressure_pa,
        density_kg_m3,
        speed_of_sound_m_s,
    }
}

/// WASM/JS entry point: ISA atmosphere at `altitude_m`.
#[wasm_bindgen]
pub fn isa_atmosphere(altitude_m: f64) -> Atmosphere {
    isa_atmosphere_native(altitude_m)
}

/// Crate version string, exposed so the JS layer can confirm the module loaded.
#[wasm_bindgen]
pub fn core_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rel(a: f64, b: f64) -> f64 {
        (a - b).abs() / b.abs().max(1e-300)
    }

    // Reference values produced by app/engine_core/atmosphere.py.
    #[test]
    fn isa_sea_level_matches_python() {
        let a = isa_atmosphere_native(0.0);
        assert!(rel(a.temperature_k, 288.15) < 1e-12);
        assert!(rel(a.pressure_pa, 101325.0) < 1e-12);
        assert!(rel(a.density_kg_m3, 1.2252256827617731) < 1e-9);
        assert!(rel(a.speed_of_sound_m_s, 340.2626485525556) < 1e-9);
    }

    #[test]
    fn isa_troposphere_10km_matches_python() {
        let a = isa_atmosphere_native(10000.0);
        assert!(rel(a.temperature_k, 223.14999999999998) < 1e-12);
        assert!(rel(a.pressure_pa, 26429.700111057547) < 1e-9);
        assert!(rel(a.density_kg_m3, 0.4126800243122905) < 1e-9);
        assert!(rel(a.speed_of_sound_m_s, 299.4355857275484) < 1e-9);
    }

    #[test]
    fn isa_stratosphere_20km_matches_python() {
        let a = isa_atmosphere_native(20000.0);
        assert!(rel(a.temperature_k, 216.64999999999998) < 1e-12);
        assert!(rel(a.pressure_pa, 5471.9350719501235) < 1e-9);
        assert!(rel(a.density_kg_m3, 0.08800358116987489) < 1e-9);
    }
}

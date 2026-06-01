/* wasm-engine.js — client-side cycle compute with a Python-API fallback.
 *
 * Day 68-69: a thin integration layer over the WASM core (propulsion_core.js).
 * `runCycle()` runs the cycle locally in WebAssembly when the engine + options
 * are supported by the Rust port, and otherwise (or on any load/compute error)
 * falls back to the FastAPI Python solver, which stays the source of truth.
 * Results are normalised to the same keys the API returns, so callers are
 * source-agnostic.
 *
 * The WASM port covers: the dry turbojet, and the separate-flow turbofan with
 * no afterburner / no bleed-cooling / no open third stream. Everything else
 * routes to the API automatically.
 */

let _module = null;
let _loading = null;
let _failed = false;

const GLUE_URL = "/lab/wasm/propulsion-core/propulsion_core.js";

/** Lazy-load + initialise the WASM module once. Returns null if it cannot load. */
export async function loadWasm() {
  if (_module) return _module;
  if (_failed) return null;
  if (!_loading) {
    _loading = import(GLUE_URL)
      .then(async (mod) => {
        await mod.default(); // init() — fetch + instantiate the .wasm
        _module = mod;
        return mod;
      })
      .catch((err) => {
        _failed = true;
        console.warn("WASM core unavailable, falling back to API:", err);
        return null;
      });
  }
  return _loading;
}

/** True when the Rust port can handle this engine + option set. */
export function wasmSupports(family, inputs) {
  if (family === "turbojet") {
    return (inputs.engine_variant || "turbojet") === "turbojet";
  }
  if (family === "turbofan") {
    const thirdOpen =
      inputs.third_stream &&
      (inputs.variable_cycle_mode || "high_efficiency") === "high_efficiency" &&
      Number(inputs.third_stream_ratio) > 0;
    return (
      (inputs.nozzle_configuration || "separate") === "separate" &&
      !inputs.use_afterburner &&
      !(Number(inputs.bleed_fraction_hpc_exit) > 0) &&
      !(Number(inputs.cooling_fraction_hpt_inlet) > 0) &&
      !thirdOpen
    );
  }
  return false;
}

function runTurbojetWasm(mod, i) {
  const o = mod.turbojet_cycle(
    i.altitude_m, i.mach, i.mass_flow_air_kg_s,
    i.compressor_pressure_ratio, i.compressor_efficiency,
    i.turbine_inlet_temperature_K, i.turbine_efficiency,
    i.combustor_efficiency, i.combustor_pressure_loss_fraction,
    i.mechanical_efficiency, i.nozzle_efficiency,
    i.inlet_pressure_recovery, i.fuel_heating_value_J_kg,
  );
  return {
    engine_type: "turbojet",
    thrust_N: o.thrust_n,
    thrust_kN: o.thrust_kn,
    specific_thrust_N_per_kg_s: o.specific_thrust_n_per_kg_s,
    fuel_air_ratio: o.fuel_air_ratio,
    fuel_flow_kg_s: o.fuel_flow_kg_s,
    TSFC_kg_per_N_s: o.tsfc_kg_per_n_s,
    TSFC_kg_per_kN_hr: o.tsfc_kg_per_kn_hr,
    momentum_thrust_N: o.momentum_thrust_n,
    pressure_thrust_N: o.pressure_thrust_n,
    exit_velocity_m_s: o.exit_velocity_m_s,
    nozzle_exit_pressure_Pa: o.nozzle_exit_pressure_pa,
    nozzle_choked: o.nozzle_choked,
    thermal_efficiency_estimate: o.thermal_efficiency_estimate,
    propulsive_efficiency_estimate: o.propulsive_efficiency_estimate,
    overall_efficiency_estimate: o.overall_efficiency_estimate,
    _source: "wasm",
  };
}

function runTurbofanWasm(mod, i) {
  const o = mod.turbofan_cycle(
    i.altitude_m, i.mach, i.total_mass_flow_air_kg_s, i.bypass_ratio,
    i.fan_pressure_ratio, i.fan_efficiency,
    i.core_compressor_pressure_ratio, i.compressor_efficiency,
    i.turbine_inlet_temperature_K, i.hp_turbine_efficiency, i.lp_turbine_efficiency,
    i.combustor_efficiency, i.combustor_pressure_loss_fraction, i.mechanical_efficiency,
    i.core_nozzle_efficiency, i.bypass_nozzle_efficiency,
    i.inlet_pressure_recovery, i.fuel_heating_value_J_kg,
  );
  return {
    engine_type: "turbofan",
    thrust_N: o.thrust_n,
    thrust_kN: o.thrust_kn,
    core_thrust_N: o.core_thrust_n,
    bypass_thrust_N: o.bypass_thrust_n,
    specific_thrust_N_per_kg_s: o.specific_thrust_n_per_kg_s,
    fuel_air_ratio: o.fuel_air_ratio,
    fuel_flow_kg_s: o.fuel_flow_kg_s,
    TSFC_kg_per_kN_hr: o.tsfc_kg_per_kn_hr,
    exit_velocity_m_s: o.exit_velocity_m_s,
    bypass_exit_velocity_m_s: o.bypass_exit_velocity_m_s,
    momentum_thrust_N: o.momentum_thrust_n,
    pressure_thrust_N: o.pressure_thrust_n,
    nozzle_choked: o.nozzle_choked,
    bypass_nozzle_choked: o.bypass_nozzle_choked,
    thermal_efficiency_estimate: o.thermal_efficiency_estimate,
    propulsive_efficiency_estimate: o.propulsive_efficiency_estimate,
    overall_efficiency_estimate: o.overall_efficiency_estimate,
    _source: "wasm",
  };
}

/** Run one cycle synchronously in WASM (caller guarantees support + loaded). */
export function runWasm(mod, family, inputs) {
  return family === "turbojet"
    ? runTurbojetWasm(mod, inputs)
    : runTurbofanWasm(mod, inputs);
}

/** Run via the Python API. Returns the parsed result (tagged _source: "api"). */
export async function runApi(family, inputs) {
  const res = await fetch(`/simulate/${family}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(inputs),
  });
  const payload = await res.json();
  if (!res.ok) throw new Error(payload.detail || "API request failed");
  payload._source = "api";
  return payload;
}

/**
 * Compute a cycle. When `preferWasm` and the config is supported, runs locally
 * in WASM; otherwise falls back to the API. Always resolves to a normalised
 * result with `_source` set to "wasm" or "api".
 */
export async function runCycle(family, inputs, { preferWasm = true } = {}) {
  if (preferWasm && wasmSupports(family, inputs)) {
    const mod = await loadWasm();
    if (mod) {
      try {
        return runWasm(mod, family, inputs);
      } catch (err) {
        console.warn("WASM compute failed, falling back to API:", err);
      }
    }
  }
  return runApi(family, inputs);
}

/**
 * Latency benchmark: mean per-call time for WASM (local) vs the API
 * (round-trip), plus the parity error between them. The speed-up is the
 * end-to-end latency ratio — the real win is eliminating the network round
 * trip, not just raw arithmetic.
 */
export async function benchmark(family, inputs, { wasmIters = 5000, apiIters = 25 } = {}) {
  const mod = await loadWasm();
  const out = { supported: wasmSupports(family, inputs) && Boolean(mod) };

  if (out.supported) {
    let wasmRes = null;
    // warm-up
    for (let k = 0; k < 50; k += 1) wasmRes = runWasm(mod, family, inputs);
    const t0 = performance.now();
    for (let k = 0; k < wasmIters; k += 1) wasmRes = runWasm(mod, family, inputs);
    out.wasmMsPerCall = (performance.now() - t0) / wasmIters;
    out.wasmResult = wasmRes;
  }

  let apiRes = null;
  const t1 = performance.now();
  for (let k = 0; k < apiIters; k += 1) apiRes = await runApi(family, inputs);
  out.apiMsPerCall = (performance.now() - t1) / apiIters;
  out.apiResult = apiRes;

  if (out.supported) {
    out.speedup = out.apiMsPerCall / out.wasmMsPerCall;
    out.parityError = Math.abs(out.wasmResult.thrust_kN - apiRes.thrust_kN) /
      Math.max(Math.abs(apiRes.thrust_kN), 1e-300);
  }
  return out;
}

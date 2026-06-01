/* tslint:disable */
/* eslint-disable */

/**
 * Static ambient atmosphere state (mirror of the Python `AtmosphereState`).
 */
export class Atmosphere {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    density_kg_m3: number;
    pressure_pa: number;
    speed_of_sound_m_s: number;
    temperature_k: number;
}

export class CombustorOut {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    fuel_air_ratio: number;
    pt4_pa: number;
}

export class CompressorOut {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    pt3_pa: number;
    specific_work_j_kg: number;
    tt3_k: number;
    tt3s_k: number;
}

export class TurbineOut {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    pt5_pa: number;
    tt5_k: number;
    tt5s_k: number;
}

/**
 * Headline separate-flow turbofan results (mirror of the Python result dict).
 */
export class TurbofanOut {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    bypass_exit_velocity_m_s: number;
    bypass_nozzle_choked: boolean;
    bypass_thrust_n: number;
    core_thrust_n: number;
    exit_velocity_m_s: number;
    fuel_air_ratio: number;
    fuel_flow_kg_s: number;
    momentum_thrust_n: number;
    nozzle_choked: boolean;
    overall_efficiency_estimate: number;
    pressure_thrust_n: number;
    propulsive_efficiency_estimate: number;
    pt5_pa: number;
    specific_thrust_n_per_kg_s: number;
    thermal_efficiency_estimate: number;
    thrust_kn: number;
    thrust_n: number;
    tsfc_kg_per_kn_hr: number;
    tt5_k: number;
}

/**
 * Headline turbojet cycle results (mirror of the Python result dict's core
 * fields). Station detail kept minimal here; the full station table stays on
 * the Python side.
 */
export class TurbojetOut {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    exit_velocity_m_s: number;
    freestream_velocity_m_s: number;
    fuel_air_ratio: number;
    fuel_flow_kg_s: number;
    momentum_thrust_n: number;
    nozzle_choked: boolean;
    nozzle_exit_pressure_pa: number;
    overall_efficiency_estimate: number;
    pressure_thrust_n: number;
    propulsive_efficiency_estimate: number;
    pt5_pa: number;
    specific_thrust_n_per_kg_s: number;
    thermal_efficiency_estimate: number;
    thrust_kn: number;
    thrust_n: number;
    tsfc_kg_per_kn_hr: number;
    tsfc_kg_per_n_s: number;
    tt5_k: number;
}

export function combustor_exit(tt3_k: number, pt3_pa: number, turbine_inlet_temperature_k: number, combustor_efficiency: number, pressure_loss_fraction: number, fuel_heating_value_j_kg: number): CombustorOut;

export function compressor_exit(tt2_k: number, pt2_pa: number, pressure_ratio: number, efficiency: number): CompressorOut;

/**
 * Crate version string, exposed so the JS layer can confirm the module loaded.
 */
export function core_version(): string;

/**
 * WASM/JS entry point: ISA atmosphere at `altitude_m`.
 */
export function isa_atmosphere(altitude_m: number): Atmosphere;

export function turbine_exit(tt4_k: number, pt4_pa: number, compressor_specific_work_j_kg: number, fuel_air_ratio: number, mechanical_efficiency: number, turbine_efficiency: number, gas_mass_flow_ratio?: number | null): TurbineOut;

/**
 * WASM/JS entry point for the separate-flow dry turbofan cycle.
 */
export function turbofan_cycle(altitude_m: number, mach: number, total_mass_flow_air_kg_s: number, bypass_ratio: number, fan_pressure_ratio: number, fan_efficiency: number, core_compressor_pressure_ratio: number, compressor_efficiency: number, turbine_inlet_temperature_k: number, hp_turbine_efficiency: number, lp_turbine_efficiency: number, combustor_efficiency: number, combustor_pressure_loss_fraction: number, mechanical_efficiency: number, core_nozzle_efficiency: number, bypass_nozzle_efficiency: number, inlet_pressure_recovery: number, fuel_heating_value_j_kg: number): TurbofanOut;

/**
 * WASM/JS entry point for the full dry turbojet cycle.
 */
export function turbojet_cycle(altitude_m: number, mach: number, mass_flow_air_kg_s: number, compressor_pressure_ratio: number, compressor_efficiency: number, turbine_inlet_temperature_k: number, turbine_efficiency: number, combustor_efficiency: number, combustor_pressure_loss_fraction: number, mechanical_efficiency: number, nozzle_efficiency: number, inlet_pressure_recovery: number, fuel_heating_value_j_kg: number): TurbojetOut;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly __wbg_atmosphere_free: (a: number, b: number) => void;
    readonly __wbg_combustorout_free: (a: number, b: number) => void;
    readonly __wbg_get_atmosphere_density_kg_m3: (a: number) => number;
    readonly __wbg_get_atmosphere_pressure_pa: (a: number) => number;
    readonly __wbg_get_atmosphere_speed_of_sound_m_s: (a: number) => number;
    readonly __wbg_get_atmosphere_temperature_k: (a: number) => number;
    readonly __wbg_get_turbofanout_bypass_exit_velocity_m_s: (a: number) => number;
    readonly __wbg_get_turbofanout_bypass_nozzle_choked: (a: number) => number;
    readonly __wbg_get_turbofanout_exit_velocity_m_s: (a: number) => number;
    readonly __wbg_get_turbofanout_fuel_air_ratio: (a: number) => number;
    readonly __wbg_get_turbofanout_fuel_flow_kg_s: (a: number) => number;
    readonly __wbg_get_turbofanout_momentum_thrust_n: (a: number) => number;
    readonly __wbg_get_turbofanout_nozzle_choked: (a: number) => number;
    readonly __wbg_get_turbofanout_overall_efficiency_estimate: (a: number) => number;
    readonly __wbg_get_turbofanout_pressure_thrust_n: (a: number) => number;
    readonly __wbg_get_turbofanout_propulsive_efficiency_estimate: (a: number) => number;
    readonly __wbg_get_turbofanout_pt5_pa: (a: number) => number;
    readonly __wbg_get_turbofanout_specific_thrust_n_per_kg_s: (a: number) => number;
    readonly __wbg_get_turbofanout_thermal_efficiency_estimate: (a: number) => number;
    readonly __wbg_get_turbofanout_tsfc_kg_per_kn_hr: (a: number) => number;
    readonly __wbg_get_turbofanout_tt5_k: (a: number) => number;
    readonly __wbg_set_atmosphere_density_kg_m3: (a: number, b: number) => void;
    readonly __wbg_set_atmosphere_pressure_pa: (a: number, b: number) => void;
    readonly __wbg_set_atmosphere_speed_of_sound_m_s: (a: number, b: number) => void;
    readonly __wbg_set_atmosphere_temperature_k: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_bypass_exit_velocity_m_s: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_bypass_nozzle_choked: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_exit_velocity_m_s: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_fuel_air_ratio: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_fuel_flow_kg_s: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_momentum_thrust_n: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_nozzle_choked: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_overall_efficiency_estimate: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_pressure_thrust_n: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_propulsive_efficiency_estimate: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_pt5_pa: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_specific_thrust_n_per_kg_s: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_thermal_efficiency_estimate: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_tsfc_kg_per_kn_hr: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_tt5_k: (a: number, b: number) => void;
    readonly __wbg_turbineout_free: (a: number, b: number) => void;
    readonly __wbg_turbofanout_free: (a: number, b: number) => void;
    readonly combustor_exit: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number, number];
    readonly compressor_exit: (a: number, b: number, c: number, d: number) => [number, number, number];
    readonly core_version: () => [number, number];
    readonly isa_atmosphere: (a: number) => number;
    readonly turbine_exit: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number) => [number, number, number];
    readonly turbofan_cycle: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number, j: number, k: number, l: number, m: number, n: number, o: number, p: number, q: number, r: number) => [number, number, number];
    readonly turbojet_cycle: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number, i: number, j: number, k: number, l: number, m: number) => [number, number, number];
    readonly __wbg_set_turbojetout_nozzle_choked: (a: number, b: number) => void;
    readonly __wbg_get_turbojetout_nozzle_choked: (a: number) => number;
    readonly __wbg_get_combustorout_fuel_air_ratio: (a: number) => number;
    readonly __wbg_get_combustorout_pt4_pa: (a: number) => number;
    readonly __wbg_get_compressorout_pt3_pa: (a: number) => number;
    readonly __wbg_get_compressorout_specific_work_j_kg: (a: number) => number;
    readonly __wbg_get_compressorout_tt3_k: (a: number) => number;
    readonly __wbg_get_compressorout_tt3s_k: (a: number) => number;
    readonly __wbg_get_turbineout_pt5_pa: (a: number) => number;
    readonly __wbg_get_turbineout_tt5_k: (a: number) => number;
    readonly __wbg_get_turbineout_tt5s_k: (a: number) => number;
    readonly __wbg_get_turbofanout_bypass_thrust_n: (a: number) => number;
    readonly __wbg_get_turbofanout_core_thrust_n: (a: number) => number;
    readonly __wbg_get_turbofanout_thrust_kn: (a: number) => number;
    readonly __wbg_get_turbofanout_thrust_n: (a: number) => number;
    readonly __wbg_get_turbojetout_exit_velocity_m_s: (a: number) => number;
    readonly __wbg_get_turbojetout_freestream_velocity_m_s: (a: number) => number;
    readonly __wbg_get_turbojetout_fuel_air_ratio: (a: number) => number;
    readonly __wbg_get_turbojetout_fuel_flow_kg_s: (a: number) => number;
    readonly __wbg_get_turbojetout_momentum_thrust_n: (a: number) => number;
    readonly __wbg_get_turbojetout_nozzle_exit_pressure_pa: (a: number) => number;
    readonly __wbg_get_turbojetout_overall_efficiency_estimate: (a: number) => number;
    readonly __wbg_get_turbojetout_pressure_thrust_n: (a: number) => number;
    readonly __wbg_get_turbojetout_propulsive_efficiency_estimate: (a: number) => number;
    readonly __wbg_get_turbojetout_pt5_pa: (a: number) => number;
    readonly __wbg_get_turbojetout_specific_thrust_n_per_kg_s: (a: number) => number;
    readonly __wbg_get_turbojetout_thermal_efficiency_estimate: (a: number) => number;
    readonly __wbg_get_turbojetout_thrust_kn: (a: number) => number;
    readonly __wbg_get_turbojetout_thrust_n: (a: number) => number;
    readonly __wbg_get_turbojetout_tsfc_kg_per_kn_hr: (a: number) => number;
    readonly __wbg_get_turbojetout_tsfc_kg_per_n_s: (a: number) => number;
    readonly __wbg_get_turbojetout_tt5_k: (a: number) => number;
    readonly __wbg_set_combustorout_fuel_air_ratio: (a: number, b: number) => void;
    readonly __wbg_set_combustorout_pt4_pa: (a: number, b: number) => void;
    readonly __wbg_set_compressorout_pt3_pa: (a: number, b: number) => void;
    readonly __wbg_set_compressorout_specific_work_j_kg: (a: number, b: number) => void;
    readonly __wbg_set_compressorout_tt3_k: (a: number, b: number) => void;
    readonly __wbg_set_compressorout_tt3s_k: (a: number, b: number) => void;
    readonly __wbg_set_turbineout_pt5_pa: (a: number, b: number) => void;
    readonly __wbg_set_turbineout_tt5_k: (a: number, b: number) => void;
    readonly __wbg_set_turbineout_tt5s_k: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_bypass_thrust_n: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_core_thrust_n: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_thrust_kn: (a: number, b: number) => void;
    readonly __wbg_set_turbofanout_thrust_n: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_exit_velocity_m_s: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_freestream_velocity_m_s: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_fuel_air_ratio: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_fuel_flow_kg_s: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_momentum_thrust_n: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_nozzle_exit_pressure_pa: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_overall_efficiency_estimate: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_pressure_thrust_n: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_propulsive_efficiency_estimate: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_pt5_pa: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_specific_thrust_n_per_kg_s: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_thermal_efficiency_estimate: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_thrust_kn: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_thrust_n: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_tsfc_kg_per_kn_hr: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_tsfc_kg_per_n_s: (a: number, b: number) => void;
    readonly __wbg_set_turbojetout_tt5_k: (a: number, b: number) => void;
    readonly __wbg_turbojetout_free: (a: number, b: number) => void;
    readonly __wbg_compressorout_free: (a: number, b: number) => void;
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __externref_table_dealloc: (a: number) => void;
    readonly __wbindgen_free: (a: number, b: number, c: number) => void;
    readonly __wbindgen_start: () => void;
}

export type SyncInitInput = BufferSource | WebAssembly.Module;

/**
 * Instantiates the given `module`, which can either be bytes or
 * a precompiled `WebAssembly.Module`.
 *
 * @param {{ module: SyncInitInput }} module - Passing `SyncInitInput` directly is deprecated.
 *
 * @returns {InitOutput}
 */
export function initSync(module: { module: SyncInitInput } | SyncInitInput): InitOutput;

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
export default function __wbg_init (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;

/* @ts-self-types="./propulsion_core.d.ts" */

/**
 * Static ambient atmosphere state (mirror of the Python `AtmosphereState`).
 */
export class Atmosphere {
    static __wrap(ptr) {
        const obj = Object.create(Atmosphere.prototype);
        obj.__wbg_ptr = ptr;
        AtmosphereFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        AtmosphereFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_atmosphere_free(ptr, 0);
    }
    /**
     * @returns {number}
     */
    get density_kg_m3() {
        const ret = wasm.__wbg_get_atmosphere_density_kg_m3(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get pressure_pa() {
        const ret = wasm.__wbg_get_atmosphere_pressure_pa(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get speed_of_sound_m_s() {
        const ret = wasm.__wbg_get_atmosphere_speed_of_sound_m_s(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get temperature_k() {
        const ret = wasm.__wbg_get_atmosphere_temperature_k(this.__wbg_ptr);
        return ret;
    }
    /**
     * @param {number} arg0
     */
    set density_kg_m3(arg0) {
        wasm.__wbg_set_atmosphere_density_kg_m3(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set pressure_pa(arg0) {
        wasm.__wbg_set_atmosphere_pressure_pa(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set speed_of_sound_m_s(arg0) {
        wasm.__wbg_set_atmosphere_speed_of_sound_m_s(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set temperature_k(arg0) {
        wasm.__wbg_set_atmosphere_temperature_k(this.__wbg_ptr, arg0);
    }
}
if (Symbol.dispose) Atmosphere.prototype[Symbol.dispose] = Atmosphere.prototype.free;

export class CombustorOut {
    static __wrap(ptr) {
        const obj = Object.create(CombustorOut.prototype);
        obj.__wbg_ptr = ptr;
        CombustorOutFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        CombustorOutFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_combustorout_free(ptr, 0);
    }
    /**
     * @returns {number}
     */
    get fuel_air_ratio() {
        const ret = wasm.__wbg_get_combustorout_fuel_air_ratio(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get pt4_pa() {
        const ret = wasm.__wbg_get_combustorout_pt4_pa(this.__wbg_ptr);
        return ret;
    }
    /**
     * @param {number} arg0
     */
    set fuel_air_ratio(arg0) {
        wasm.__wbg_set_combustorout_fuel_air_ratio(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set pt4_pa(arg0) {
        wasm.__wbg_set_combustorout_pt4_pa(this.__wbg_ptr, arg0);
    }
}
if (Symbol.dispose) CombustorOut.prototype[Symbol.dispose] = CombustorOut.prototype.free;

export class CompressorOut {
    static __wrap(ptr) {
        const obj = Object.create(CompressorOut.prototype);
        obj.__wbg_ptr = ptr;
        CompressorOutFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        CompressorOutFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_compressorout_free(ptr, 0);
    }
    /**
     * @returns {number}
     */
    get pt3_pa() {
        const ret = wasm.__wbg_get_compressorout_pt3_pa(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get specific_work_j_kg() {
        const ret = wasm.__wbg_get_compressorout_specific_work_j_kg(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get tt3_k() {
        const ret = wasm.__wbg_get_compressorout_tt3_k(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get tt3s_k() {
        const ret = wasm.__wbg_get_compressorout_tt3s_k(this.__wbg_ptr);
        return ret;
    }
    /**
     * @param {number} arg0
     */
    set pt3_pa(arg0) {
        wasm.__wbg_set_compressorout_pt3_pa(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set specific_work_j_kg(arg0) {
        wasm.__wbg_set_compressorout_specific_work_j_kg(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set tt3_k(arg0) {
        wasm.__wbg_set_compressorout_tt3_k(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set tt3s_k(arg0) {
        wasm.__wbg_set_compressorout_tt3s_k(this.__wbg_ptr, arg0);
    }
}
if (Symbol.dispose) CompressorOut.prototype[Symbol.dispose] = CompressorOut.prototype.free;

export class TurbineOut {
    static __wrap(ptr) {
        const obj = Object.create(TurbineOut.prototype);
        obj.__wbg_ptr = ptr;
        TurbineOutFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        TurbineOutFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_turbineout_free(ptr, 0);
    }
    /**
     * @returns {number}
     */
    get pt5_pa() {
        const ret = wasm.__wbg_get_turbineout_pt5_pa(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get tt5_k() {
        const ret = wasm.__wbg_get_turbineout_tt5_k(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get tt5s_k() {
        const ret = wasm.__wbg_get_turbineout_tt5s_k(this.__wbg_ptr);
        return ret;
    }
    /**
     * @param {number} arg0
     */
    set pt5_pa(arg0) {
        wasm.__wbg_set_turbineout_pt5_pa(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set tt5_k(arg0) {
        wasm.__wbg_set_turbineout_tt5_k(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set tt5s_k(arg0) {
        wasm.__wbg_set_turbineout_tt5s_k(this.__wbg_ptr, arg0);
    }
}
if (Symbol.dispose) TurbineOut.prototype[Symbol.dispose] = TurbineOut.prototype.free;

/**
 * Headline separate-flow turbofan results (mirror of the Python result dict).
 */
export class TurbofanOut {
    static __wrap(ptr) {
        const obj = Object.create(TurbofanOut.prototype);
        obj.__wbg_ptr = ptr;
        TurbofanOutFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        TurbofanOutFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_turbofanout_free(ptr, 0);
    }
    /**
     * @returns {number}
     */
    get bypass_exit_velocity_m_s() {
        const ret = wasm.__wbg_get_turbofanout_bypass_exit_velocity_m_s(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {boolean}
     */
    get bypass_nozzle_choked() {
        const ret = wasm.__wbg_get_turbofanout_bypass_nozzle_choked(this.__wbg_ptr);
        return ret !== 0;
    }
    /**
     * @returns {number}
     */
    get bypass_thrust_n() {
        const ret = wasm.__wbg_get_turbofanout_bypass_thrust_n(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get core_thrust_n() {
        const ret = wasm.__wbg_get_turbofanout_core_thrust_n(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get exit_velocity_m_s() {
        const ret = wasm.__wbg_get_turbofanout_exit_velocity_m_s(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get fuel_air_ratio() {
        const ret = wasm.__wbg_get_turbofanout_fuel_air_ratio(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get fuel_flow_kg_s() {
        const ret = wasm.__wbg_get_turbofanout_fuel_flow_kg_s(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get momentum_thrust_n() {
        const ret = wasm.__wbg_get_turbofanout_momentum_thrust_n(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {boolean}
     */
    get nozzle_choked() {
        const ret = wasm.__wbg_get_turbofanout_nozzle_choked(this.__wbg_ptr);
        return ret !== 0;
    }
    /**
     * @returns {number}
     */
    get overall_efficiency_estimate() {
        const ret = wasm.__wbg_get_turbofanout_overall_efficiency_estimate(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get pressure_thrust_n() {
        const ret = wasm.__wbg_get_turbofanout_pressure_thrust_n(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get propulsive_efficiency_estimate() {
        const ret = wasm.__wbg_get_turbofanout_propulsive_efficiency_estimate(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get pt5_pa() {
        const ret = wasm.__wbg_get_turbofanout_pt5_pa(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get specific_thrust_n_per_kg_s() {
        const ret = wasm.__wbg_get_turbofanout_specific_thrust_n_per_kg_s(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get thermal_efficiency_estimate() {
        const ret = wasm.__wbg_get_turbofanout_thermal_efficiency_estimate(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get thrust_kn() {
        const ret = wasm.__wbg_get_turbofanout_thrust_kn(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get thrust_n() {
        const ret = wasm.__wbg_get_turbofanout_thrust_n(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get tsfc_kg_per_kn_hr() {
        const ret = wasm.__wbg_get_turbofanout_tsfc_kg_per_kn_hr(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get tt5_k() {
        const ret = wasm.__wbg_get_turbofanout_tt5_k(this.__wbg_ptr);
        return ret;
    }
    /**
     * @param {number} arg0
     */
    set bypass_exit_velocity_m_s(arg0) {
        wasm.__wbg_set_turbofanout_bypass_exit_velocity_m_s(this.__wbg_ptr, arg0);
    }
    /**
     * @param {boolean} arg0
     */
    set bypass_nozzle_choked(arg0) {
        wasm.__wbg_set_turbofanout_bypass_nozzle_choked(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set bypass_thrust_n(arg0) {
        wasm.__wbg_set_turbofanout_bypass_thrust_n(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set core_thrust_n(arg0) {
        wasm.__wbg_set_turbofanout_core_thrust_n(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set exit_velocity_m_s(arg0) {
        wasm.__wbg_set_turbofanout_exit_velocity_m_s(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set fuel_air_ratio(arg0) {
        wasm.__wbg_set_turbofanout_fuel_air_ratio(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set fuel_flow_kg_s(arg0) {
        wasm.__wbg_set_turbofanout_fuel_flow_kg_s(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set momentum_thrust_n(arg0) {
        wasm.__wbg_set_turbofanout_momentum_thrust_n(this.__wbg_ptr, arg0);
    }
    /**
     * @param {boolean} arg0
     */
    set nozzle_choked(arg0) {
        wasm.__wbg_set_turbofanout_nozzle_choked(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set overall_efficiency_estimate(arg0) {
        wasm.__wbg_set_turbofanout_overall_efficiency_estimate(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set pressure_thrust_n(arg0) {
        wasm.__wbg_set_turbofanout_pressure_thrust_n(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set propulsive_efficiency_estimate(arg0) {
        wasm.__wbg_set_turbofanout_propulsive_efficiency_estimate(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set pt5_pa(arg0) {
        wasm.__wbg_set_turbofanout_pt5_pa(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set specific_thrust_n_per_kg_s(arg0) {
        wasm.__wbg_set_turbofanout_specific_thrust_n_per_kg_s(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set thermal_efficiency_estimate(arg0) {
        wasm.__wbg_set_turbofanout_thermal_efficiency_estimate(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set thrust_kn(arg0) {
        wasm.__wbg_set_turbofanout_thrust_kn(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set thrust_n(arg0) {
        wasm.__wbg_set_turbofanout_thrust_n(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set tsfc_kg_per_kn_hr(arg0) {
        wasm.__wbg_set_turbofanout_tsfc_kg_per_kn_hr(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set tt5_k(arg0) {
        wasm.__wbg_set_turbofanout_tt5_k(this.__wbg_ptr, arg0);
    }
}
if (Symbol.dispose) TurbofanOut.prototype[Symbol.dispose] = TurbofanOut.prototype.free;

/**
 * Headline turbojet cycle results (mirror of the Python result dict's core
 * fields). Station detail kept minimal here; the full station table stays on
 * the Python side.
 */
export class TurbojetOut {
    static __wrap(ptr) {
        const obj = Object.create(TurbojetOut.prototype);
        obj.__wbg_ptr = ptr;
        TurbojetOutFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
    }
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        TurbojetOutFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_turbojetout_free(ptr, 0);
    }
    /**
     * @returns {number}
     */
    get exit_velocity_m_s() {
        const ret = wasm.__wbg_get_turbojetout_exit_velocity_m_s(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get freestream_velocity_m_s() {
        const ret = wasm.__wbg_get_turbojetout_freestream_velocity_m_s(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get fuel_air_ratio() {
        const ret = wasm.__wbg_get_turbojetout_fuel_air_ratio(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get fuel_flow_kg_s() {
        const ret = wasm.__wbg_get_turbojetout_fuel_flow_kg_s(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get momentum_thrust_n() {
        const ret = wasm.__wbg_get_turbojetout_momentum_thrust_n(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {boolean}
     */
    get nozzle_choked() {
        const ret = wasm.__wbg_get_turbojetout_nozzle_choked(this.__wbg_ptr);
        return ret !== 0;
    }
    /**
     * @returns {number}
     */
    get nozzle_exit_pressure_pa() {
        const ret = wasm.__wbg_get_turbojetout_nozzle_exit_pressure_pa(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get overall_efficiency_estimate() {
        const ret = wasm.__wbg_get_turbojetout_overall_efficiency_estimate(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get pressure_thrust_n() {
        const ret = wasm.__wbg_get_turbojetout_pressure_thrust_n(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get propulsive_efficiency_estimate() {
        const ret = wasm.__wbg_get_turbojetout_propulsive_efficiency_estimate(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get pt5_pa() {
        const ret = wasm.__wbg_get_turbojetout_pt5_pa(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get specific_thrust_n_per_kg_s() {
        const ret = wasm.__wbg_get_turbojetout_specific_thrust_n_per_kg_s(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get thermal_efficiency_estimate() {
        const ret = wasm.__wbg_get_turbojetout_thermal_efficiency_estimate(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get thrust_kn() {
        const ret = wasm.__wbg_get_turbojetout_thrust_kn(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get thrust_n() {
        const ret = wasm.__wbg_get_turbojetout_thrust_n(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get tsfc_kg_per_kn_hr() {
        const ret = wasm.__wbg_get_turbojetout_tsfc_kg_per_kn_hr(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get tsfc_kg_per_n_s() {
        const ret = wasm.__wbg_get_turbojetout_tsfc_kg_per_n_s(this.__wbg_ptr);
        return ret;
    }
    /**
     * @returns {number}
     */
    get tt5_k() {
        const ret = wasm.__wbg_get_turbojetout_tt5_k(this.__wbg_ptr);
        return ret;
    }
    /**
     * @param {number} arg0
     */
    set exit_velocity_m_s(arg0) {
        wasm.__wbg_set_turbojetout_exit_velocity_m_s(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set freestream_velocity_m_s(arg0) {
        wasm.__wbg_set_turbojetout_freestream_velocity_m_s(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set fuel_air_ratio(arg0) {
        wasm.__wbg_set_turbojetout_fuel_air_ratio(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set fuel_flow_kg_s(arg0) {
        wasm.__wbg_set_turbojetout_fuel_flow_kg_s(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set momentum_thrust_n(arg0) {
        wasm.__wbg_set_turbojetout_momentum_thrust_n(this.__wbg_ptr, arg0);
    }
    /**
     * @param {boolean} arg0
     */
    set nozzle_choked(arg0) {
        wasm.__wbg_set_turbojetout_nozzle_choked(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set nozzle_exit_pressure_pa(arg0) {
        wasm.__wbg_set_turbojetout_nozzle_exit_pressure_pa(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set overall_efficiency_estimate(arg0) {
        wasm.__wbg_set_turbojetout_overall_efficiency_estimate(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set pressure_thrust_n(arg0) {
        wasm.__wbg_set_turbojetout_pressure_thrust_n(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set propulsive_efficiency_estimate(arg0) {
        wasm.__wbg_set_turbojetout_propulsive_efficiency_estimate(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set pt5_pa(arg0) {
        wasm.__wbg_set_turbojetout_pt5_pa(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set specific_thrust_n_per_kg_s(arg0) {
        wasm.__wbg_set_turbojetout_specific_thrust_n_per_kg_s(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set thermal_efficiency_estimate(arg0) {
        wasm.__wbg_set_turbojetout_thermal_efficiency_estimate(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set thrust_kn(arg0) {
        wasm.__wbg_set_turbojetout_thrust_kn(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set thrust_n(arg0) {
        wasm.__wbg_set_turbojetout_thrust_n(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set tsfc_kg_per_kn_hr(arg0) {
        wasm.__wbg_set_turbojetout_tsfc_kg_per_kn_hr(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set tsfc_kg_per_n_s(arg0) {
        wasm.__wbg_set_turbojetout_tsfc_kg_per_n_s(this.__wbg_ptr, arg0);
    }
    /**
     * @param {number} arg0
     */
    set tt5_k(arg0) {
        wasm.__wbg_set_turbojetout_tt5_k(this.__wbg_ptr, arg0);
    }
}
if (Symbol.dispose) TurbojetOut.prototype[Symbol.dispose] = TurbojetOut.prototype.free;

/**
 * @param {number} tt3_k
 * @param {number} pt3_pa
 * @param {number} turbine_inlet_temperature_k
 * @param {number} combustor_efficiency
 * @param {number} pressure_loss_fraction
 * @param {number} fuel_heating_value_j_kg
 * @returns {CombustorOut}
 */
export function combustor_exit(tt3_k, pt3_pa, turbine_inlet_temperature_k, combustor_efficiency, pressure_loss_fraction, fuel_heating_value_j_kg) {
    const ret = wasm.combustor_exit(tt3_k, pt3_pa, turbine_inlet_temperature_k, combustor_efficiency, pressure_loss_fraction, fuel_heating_value_j_kg);
    if (ret[2]) {
        throw takeFromExternrefTable0(ret[1]);
    }
    return CombustorOut.__wrap(ret[0]);
}

/**
 * @param {number} tt2_k
 * @param {number} pt2_pa
 * @param {number} pressure_ratio
 * @param {number} efficiency
 * @returns {CompressorOut}
 */
export function compressor_exit(tt2_k, pt2_pa, pressure_ratio, efficiency) {
    const ret = wasm.compressor_exit(tt2_k, pt2_pa, pressure_ratio, efficiency);
    if (ret[2]) {
        throw takeFromExternrefTable0(ret[1]);
    }
    return CompressorOut.__wrap(ret[0]);
}

/**
 * Crate version string, exposed so the JS layer can confirm the module loaded.
 * @returns {string}
 */
export function core_version() {
    let deferred1_0;
    let deferred1_1;
    try {
        const ret = wasm.core_version();
        deferred1_0 = ret[0];
        deferred1_1 = ret[1];
        return getStringFromWasm0(ret[0], ret[1]);
    } finally {
        wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
    }
}

/**
 * WASM/JS entry point: ISA atmosphere at `altitude_m`.
 * @param {number} altitude_m
 * @returns {Atmosphere}
 */
export function isa_atmosphere(altitude_m) {
    const ret = wasm.isa_atmosphere(altitude_m);
    return Atmosphere.__wrap(ret);
}

/**
 * @param {number} tt4_k
 * @param {number} pt4_pa
 * @param {number} compressor_specific_work_j_kg
 * @param {number} fuel_air_ratio
 * @param {number} mechanical_efficiency
 * @param {number} turbine_efficiency
 * @param {number | null} [gas_mass_flow_ratio]
 * @returns {TurbineOut}
 */
export function turbine_exit(tt4_k, pt4_pa, compressor_specific_work_j_kg, fuel_air_ratio, mechanical_efficiency, turbine_efficiency, gas_mass_flow_ratio) {
    const ret = wasm.turbine_exit(tt4_k, pt4_pa, compressor_specific_work_j_kg, fuel_air_ratio, mechanical_efficiency, turbine_efficiency, !isLikeNone(gas_mass_flow_ratio), isLikeNone(gas_mass_flow_ratio) ? 0 : gas_mass_flow_ratio);
    if (ret[2]) {
        throw takeFromExternrefTable0(ret[1]);
    }
    return TurbineOut.__wrap(ret[0]);
}

/**
 * WASM/JS entry point for the separate-flow dry turbofan cycle.
 * @param {number} altitude_m
 * @param {number} mach
 * @param {number} total_mass_flow_air_kg_s
 * @param {number} bypass_ratio
 * @param {number} fan_pressure_ratio
 * @param {number} fan_efficiency
 * @param {number} core_compressor_pressure_ratio
 * @param {number} compressor_efficiency
 * @param {number} turbine_inlet_temperature_k
 * @param {number} hp_turbine_efficiency
 * @param {number} lp_turbine_efficiency
 * @param {number} combustor_efficiency
 * @param {number} combustor_pressure_loss_fraction
 * @param {number} mechanical_efficiency
 * @param {number} core_nozzle_efficiency
 * @param {number} bypass_nozzle_efficiency
 * @param {number} inlet_pressure_recovery
 * @param {number} fuel_heating_value_j_kg
 * @returns {TurbofanOut}
 */
export function turbofan_cycle(altitude_m, mach, total_mass_flow_air_kg_s, bypass_ratio, fan_pressure_ratio, fan_efficiency, core_compressor_pressure_ratio, compressor_efficiency, turbine_inlet_temperature_k, hp_turbine_efficiency, lp_turbine_efficiency, combustor_efficiency, combustor_pressure_loss_fraction, mechanical_efficiency, core_nozzle_efficiency, bypass_nozzle_efficiency, inlet_pressure_recovery, fuel_heating_value_j_kg) {
    const ret = wasm.turbofan_cycle(altitude_m, mach, total_mass_flow_air_kg_s, bypass_ratio, fan_pressure_ratio, fan_efficiency, core_compressor_pressure_ratio, compressor_efficiency, turbine_inlet_temperature_k, hp_turbine_efficiency, lp_turbine_efficiency, combustor_efficiency, combustor_pressure_loss_fraction, mechanical_efficiency, core_nozzle_efficiency, bypass_nozzle_efficiency, inlet_pressure_recovery, fuel_heating_value_j_kg);
    if (ret[2]) {
        throw takeFromExternrefTable0(ret[1]);
    }
    return TurbofanOut.__wrap(ret[0]);
}

/**
 * WASM/JS entry point for the full dry turbojet cycle.
 * @param {number} altitude_m
 * @param {number} mach
 * @param {number} mass_flow_air_kg_s
 * @param {number} compressor_pressure_ratio
 * @param {number} compressor_efficiency
 * @param {number} turbine_inlet_temperature_k
 * @param {number} turbine_efficiency
 * @param {number} combustor_efficiency
 * @param {number} combustor_pressure_loss_fraction
 * @param {number} mechanical_efficiency
 * @param {number} nozzle_efficiency
 * @param {number} inlet_pressure_recovery
 * @param {number} fuel_heating_value_j_kg
 * @returns {TurbojetOut}
 */
export function turbojet_cycle(altitude_m, mach, mass_flow_air_kg_s, compressor_pressure_ratio, compressor_efficiency, turbine_inlet_temperature_k, turbine_efficiency, combustor_efficiency, combustor_pressure_loss_fraction, mechanical_efficiency, nozzle_efficiency, inlet_pressure_recovery, fuel_heating_value_j_kg) {
    const ret = wasm.turbojet_cycle(altitude_m, mach, mass_flow_air_kg_s, compressor_pressure_ratio, compressor_efficiency, turbine_inlet_temperature_k, turbine_efficiency, combustor_efficiency, combustor_pressure_loss_fraction, mechanical_efficiency, nozzle_efficiency, inlet_pressure_recovery, fuel_heating_value_j_kg);
    if (ret[2]) {
        throw takeFromExternrefTable0(ret[1]);
    }
    return TurbojetOut.__wrap(ret[0]);
}
function __wbg_get_imports() {
    const import0 = {
        __proto__: null,
        __wbg___wbindgen_throw_1506f2235d1bdba0: function(arg0, arg1) {
            throw new Error(getStringFromWasm0(arg0, arg1));
        },
        __wbindgen_cast_0000000000000001: function(arg0, arg1) {
            // Cast intrinsic for `Ref(String) -> Externref`.
            const ret = getStringFromWasm0(arg0, arg1);
            return ret;
        },
        __wbindgen_init_externref_table: function() {
            const table = wasm.__wbindgen_externrefs;
            const offset = table.grow(4);
            table.set(0, undefined);
            table.set(offset + 0, undefined);
            table.set(offset + 1, null);
            table.set(offset + 2, true);
            table.set(offset + 3, false);
        },
    };
    return {
        __proto__: null,
        "./propulsion_core_bg.js": import0,
    };
}

const AtmosphereFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_atmosphere_free(ptr, 1));
const CombustorOutFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_combustorout_free(ptr, 1));
const CompressorOutFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_compressorout_free(ptr, 1));
const TurbineOutFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_turbineout_free(ptr, 1));
const TurbofanOutFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_turbofanout_free(ptr, 1));
const TurbojetOutFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_turbojetout_free(ptr, 1));

function getStringFromWasm0(ptr, len) {
    return decodeText(ptr >>> 0, len);
}

let cachedUint8ArrayMemory0 = null;
function getUint8ArrayMemory0() {
    if (cachedUint8ArrayMemory0 === null || cachedUint8ArrayMemory0.byteLength === 0) {
        cachedUint8ArrayMemory0 = new Uint8Array(wasm.memory.buffer);
    }
    return cachedUint8ArrayMemory0;
}

function isLikeNone(x) {
    return x === undefined || x === null;
}

function takeFromExternrefTable0(idx) {
    const value = wasm.__wbindgen_externrefs.get(idx);
    wasm.__externref_table_dealloc(idx);
    return value;
}

let cachedTextDecoder = new TextDecoder('utf-8', { ignoreBOM: true, fatal: true });
cachedTextDecoder.decode();
const MAX_SAFARI_DECODE_BYTES = 2146435072;
let numBytesDecoded = 0;
function decodeText(ptr, len) {
    numBytesDecoded += len;
    if (numBytesDecoded >= MAX_SAFARI_DECODE_BYTES) {
        cachedTextDecoder = new TextDecoder('utf-8', { ignoreBOM: true, fatal: true });
        cachedTextDecoder.decode();
        numBytesDecoded = len;
    }
    return cachedTextDecoder.decode(getUint8ArrayMemory0().subarray(ptr, ptr + len));
}

let wasmModule, wasmInstance, wasm;
function __wbg_finalize_init(instance, module) {
    wasmInstance = instance;
    wasm = instance.exports;
    wasmModule = module;
    cachedUint8ArrayMemory0 = null;
    wasm.__wbindgen_start();
    return wasm;
}

async function __wbg_load(module, imports) {
    if (typeof Response === 'function' && module instanceof Response) {
        if (typeof WebAssembly.instantiateStreaming === 'function') {
            try {
                return await WebAssembly.instantiateStreaming(module, imports);
            } catch (e) {
                const validResponse = module.ok && expectedResponseType(module.type);

                if (validResponse && module.headers.get('Content-Type') !== 'application/wasm') {
                    console.warn("`WebAssembly.instantiateStreaming` failed because your server does not serve Wasm with `application/wasm` MIME type. Falling back to `WebAssembly.instantiate` which is slower. Original error:\n", e);

                } else { throw e; }
            }
        }

        const bytes = await module.arrayBuffer();
        return await WebAssembly.instantiate(bytes, imports);
    } else {
        const instance = await WebAssembly.instantiate(module, imports);

        if (instance instanceof WebAssembly.Instance) {
            return { instance, module };
        } else {
            return instance;
        }
    }

    function expectedResponseType(type) {
        switch (type) {
            case 'basic': case 'cors': case 'default': return true;
        }
        return false;
    }
}

function initSync(module) {
    if (wasm !== undefined) return wasm;


    if (module !== undefined) {
        if (Object.getPrototypeOf(module) === Object.prototype) {
            ({module} = module)
        } else {
            console.warn('using deprecated parameters for `initSync()`; pass a single object instead')
        }
    }

    const imports = __wbg_get_imports();
    if (!(module instanceof WebAssembly.Module)) {
        module = new WebAssembly.Module(module);
    }
    const instance = new WebAssembly.Instance(module, imports);
    return __wbg_finalize_init(instance, module);
}

async function __wbg_init(module_or_path) {
    if (wasm !== undefined) return wasm;


    if (module_or_path !== undefined) {
        if (Object.getPrototypeOf(module_or_path) === Object.prototype) {
            ({module_or_path} = module_or_path)
        } else {
            console.warn('using deprecated parameters for the initialization function; pass a single object instead')
        }
    }

    if (module_or_path === undefined) {
        module_or_path = new URL('propulsion_core_bg.wasm', import.meta.url);
    }
    const imports = __wbg_get_imports();

    if (typeof module_or_path === 'string' || (typeof Request === 'function' && module_or_path instanceof Request) || (typeof URL === 'function' && module_or_path instanceof URL)) {
        module_or_path = fetch(module_or_path);
    }

    const { instance, module } = await __wbg_load(await module_or_path, imports);

    return __wbg_finalize_init(instance, module);
}

export { initSync, __wbg_init as default };

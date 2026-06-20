/* =============================================================
   DAS LABS · PropulsionLab — MOBILE CONSOLE
   Ground-up phone client. Talks to the SAME SI backend as the
   desktop console (/simulate/<engine>, /simulate/<engine>/sweep,
   /presets) and reuses the same UNIT_DEFS display layer. The
   engine field metadata below mirrors app.js so the two stay in
   sync; the UI itself shares nothing with the desktop DOM.
   ============================================================= */
(() => {
  "use strict";

  /* ----------------------------------------------------------- *
   *  ENGINE METADATA  (mirrors app.js defaults + field lists)   *
   * ----------------------------------------------------------- */

  const ICONS = {
    turbojet:
      '<path d="M2 11 L12 5 L52 5 L60 11 L52 17 L12 17 Z" stroke="currentColor" stroke-width="0.9"/><line x1="22" y1="6" x2="22" y2="16" stroke="currentColor" stroke-width="0.8"/><line x1="32" y1="6" x2="32" y2="16" stroke="currentColor" stroke-width="0.8"/><line x1="42" y1="6" x2="42" y2="16" stroke="currentColor" stroke-width="0.8"/>',
    turbofan:
      '<path d="M2 11 L10 3 L52 5 L60 11 L52 17 L10 19 Z" stroke="currentColor" stroke-width="0.9"/><circle cx="10" cy="11" r="5" stroke="currentColor" stroke-width="0.8" fill="none"/><line x1="32" y1="6" x2="32" y2="16" stroke="currentColor" stroke-width="0.8"/><line x1="42" y1="6.5" x2="42" y2="15.5" stroke="currentColor" stroke-width="0.8"/>',
    turboprop:
      '<line x1="8" y1="2" x2="8" y2="20" stroke="currentColor" stroke-width="1"/><circle cx="8" cy="11" r="2.2" fill="currentColor"/><path d="M14 11 L20 6 L52 6 L58 11 L52 16 L20 16 Z" stroke="currentColor" stroke-width="0.9"/><line x1="34" y1="7" x2="34" y2="15" stroke="currentColor" stroke-width="0.8"/><line x1="44" y1="7.5" x2="44" y2="14.5" stroke="currentColor" stroke-width="0.8"/>',
    ramjet:
      '<path d="M3 5 L24 9 L40 9 L61 4 L61 18 L40 13 L24 13 L3 17 Z" stroke="currentColor" stroke-width="0.9" fill="none"/><path d="M28 8 L36 11 L28 14" stroke="currentColor" stroke-width="0.8" fill="none"/>',
    scramjet:
      '<path d="M3 18 L61 6 L61 11 L26 15 Z" stroke="currentColor" stroke-width="0.9" fill="none"/><line x1="3" y1="18" x2="61" y2="13" stroke="currentColor" stroke-width="0.7" opacity="0.7"/>',
  };

  const CONCEPTS = {
    turbojet:
      "Only a turbine to drive the compressor, and all the gas leaves as a fast jet. Simple and light but thirsty, it is the high-speed core every other family is built around.",
    turbofan:
      "A fan and a bypass duct move a large, slow stream of cold air. Most of the thrust and nearly all the efficiency of a modern airliner come from that bypass flow.",
    turboprop:
      "The turbine extracts shaft power to spin a propeller instead of leaving energy in the jet. Unbeatable efficiency at low speed, limited by propeller tip Mach.",
    ramjet:
      "No moving compressor, the flight Mach rams and compresses the air on its own. Useless below about Mach 1.5 and excellent from Mach 2 to 4, the flying stovepipe.",
    scramjet:
      "Combustion happens while the air is still supersonic, avoiding the loss of slowing it down. The frontier of Mach 5+ flight, where everything runs hot and marginal.",
  };

  const ENGINES = {
    turbojet: {
      route: "/simulate/turbojet",
      sweepRoute: "/simulate/turbojet/sweep",
      label: "Turbojet",
      code: "PL-01",
      presetTypes: ["turbojet", "afterburning_turbojet"],
      defaults: {
        engine_variant: "turbojet",
        altitude_m: 10000, mach: 0.8, mass_flow_air_kg_s: 50,
        inlet_capture_area_m2: null, use_inlet_area_mass_flow: false,
        compressor_pressure_ratio: 12, compressor_efficiency: 0.86,
        turbine_inlet_temperature_K: 1400, turbine_efficiency: 0.88,
        combustor_efficiency: 0.99, combustor_pressure_loss_fraction: 0.05,
        mechanical_efficiency: 0.99, nozzle_efficiency: 0.95,
        inlet_pressure_recovery: 0.98, fuel_heating_value_J_kg: 43000000,
        nozzle_exit_area_m2: null, nozzle_throat_area_m2: null,
        include_pressure_thrust: true,
        afterburner_exit_temperature_K: null, afterburner_efficiency: 0.95,
        afterburner_pressure_loss_fraction: 0.06, real_gas: false,
      },
      essential: ["altitude_m", "mach", "mass_flow_air_kg_s", "compressor_pressure_ratio", "turbine_inlet_temperature_K"],
      fields: [
        { key: "altitude_m", label: "Altitude", unit: "m", step: 100 },
        { key: "mach", label: "Flight Mach", unit: "", step: 0.05 },
        { key: "mass_flow_air_kg_s", label: "Air mass flow", unit: "kg/s", step: 1 },
        { key: "compressor_pressure_ratio", label: "Compressor PR", unit: "", step: 0.5 },
        { key: "turbine_inlet_temperature_K", label: "Turbine inlet T", unit: "K", step: 10 },
        { key: "compressor_efficiency", label: "Compressor η", unit: "", step: 0.01 },
        { key: "turbine_efficiency", label: "Turbine η", unit: "", step: 0.01 },
        { key: "combustor_efficiency", label: "Combustor η", unit: "", step: 0.01 },
        { key: "combustor_pressure_loss_fraction", label: "Combustor ΔP/P", unit: "", step: 0.01 },
        { key: "mechanical_efficiency", label: "Mechanical η", unit: "", step: 0.01 },
        { key: "nozzle_efficiency", label: "Nozzle η", unit: "", step: 0.01 },
        { key: "inlet_pressure_recovery", label: "Inlet recovery", unit: "", step: 0.01 },
        { key: "fuel_heating_value_J_kg", label: "Fuel LHV", unit: "J/kg", step: 1000000 },
        { key: "afterburner_exit_temperature_K", label: "Afterburner exit T", unit: "K · blank = dry", step: 10, nullable: true },
        { key: "include_pressure_thrust", label: "Include pressure thrust", type: "checkbox" },
        { key: "real_gas", label: "Real-gas chemistry", type: "checkbox" },
      ],
      sweep: {
        parameters: [
          ["compressor_pressure_ratio", "Compressor PR"],
          ["turbine_inlet_temperature_K", "Turbine inlet T"],
          ["mach", "Flight Mach"],
          ["altitude_m", "Altitude"],
          ["mass_flow_air_kg_s", "Air mass flow"],
        ],
        parameter: "compressor_pressure_ratio",
        values: "6, 9, 12, 16, 20, 25, 30",
      },
    },

    turbofan: {
      route: "/simulate/turbofan",
      sweepRoute: "/simulate/turbofan/sweep",
      label: "Turbofan",
      code: "PL-02",
      presetTypes: ["turbofan"],
      defaults: {
        nozzle_configuration: "separate",
        altitude_m: 10000, mach: 0.78, total_mass_flow_air_kg_s: 220,
        bypass_ratio: 5, fan_pressure_ratio: 1.55, fan_efficiency: 0.89,
        core_compressor_pressure_ratio: 18, compressor_efficiency: 0.88,
        turbine_inlet_temperature_K: 1550,
        hp_turbine_efficiency: 0.9, lp_turbine_efficiency: 0.9,
        combustor_efficiency: 0.99, combustor_pressure_loss_fraction: 0.05,
        mechanical_efficiency: 0.99, core_nozzle_efficiency: 0.95,
        bypass_nozzle_efficiency: 0.94, inlet_pressure_recovery: 0.98,
        fuel_heating_value_J_kg: 43000000, use_afterburner: false,
        afterburner_exit_temperature_K: 2000, afterburner_efficiency: 0.94,
        afterburner_pressure_loss_fraction: 0.08, mixer_pressure_loss_fraction: 0.02,
        third_stream: false, variable_cycle_mode: "high_efficiency",
        third_stream_ratio: 0.6, third_stream_pressure_ratio: 1.3,
        third_stream_nozzle_efficiency: 0.94,
      },
      essential: ["altitude_m", "mach", "total_mass_flow_air_kg_s", "bypass_ratio", "fan_pressure_ratio", "core_compressor_pressure_ratio", "turbine_inlet_temperature_K"],
      fields: [
        { key: "altitude_m", label: "Altitude", unit: "m", step: 100 },
        { key: "mach", label: "Flight Mach", unit: "", step: 0.02 },
        { key: "total_mass_flow_air_kg_s", label: "Total ṁ air", unit: "kg/s", step: 5 },
        { key: "bypass_ratio", label: "Bypass ratio", unit: "", step: 0.5 },
        { key: "fan_pressure_ratio", label: "Fan PR", unit: "", step: 0.05 },
        { key: "core_compressor_pressure_ratio", label: "Core HPC PR", unit: "", step: 0.5 },
        { key: "turbine_inlet_temperature_K", label: "Turbine inlet T", unit: "K", step: 10 },
        { key: "nozzle_configuration", label: "Nozzle config", unit: "", type: "select", options: [["separate", "Separate flow"], ["mixed", "Mixed flow"]] },
        { key: "fan_efficiency", label: "Fan η", unit: "", step: 0.01 },
        { key: "compressor_efficiency", label: "HPC η", unit: "", step: 0.01 },
        { key: "hp_turbine_efficiency", label: "HPT η", unit: "", step: 0.01 },
        { key: "lp_turbine_efficiency", label: "LPT η", unit: "", step: 0.01 },
        { key: "combustor_efficiency", label: "Combustor η", unit: "", step: 0.01 },
        { key: "combustor_pressure_loss_fraction", label: "Combustor ΔP/P", unit: "", step: 0.01 },
        { key: "core_nozzle_efficiency", label: "Core nozzle η", unit: "", step: 0.01 },
        { key: "bypass_nozzle_efficiency", label: "Bypass nozzle η", unit: "", step: 0.01 },
        { key: "inlet_pressure_recovery", label: "Inlet recovery", unit: "", step: 0.01 },
        { key: "use_afterburner", label: "Afterburner", type: "checkbox" },
        { key: "afterburner_exit_temperature_K", label: "AB exit T", unit: "K", step: 10 },
      ],
      sweep: {
        parameters: [
          ["bypass_ratio", "Bypass ratio"],
          ["fan_pressure_ratio", "Fan PR"],
          ["core_compressor_pressure_ratio", "Core HPC PR"],
          ["turbine_inlet_temperature_K", "Turbine inlet T"],
          ["mach", "Flight Mach"],
          ["altitude_m", "Altitude"],
        ],
        parameter: "bypass_ratio",
        values: "1, 3, 5, 8, 11",
      },
    },

    turboprop: {
      route: "/simulate/turboprop",
      sweepRoute: "/simulate/turboprop/sweep",
      label: "Turboprop",
      code: "PL-03",
      presetTypes: ["turboprop"],
      defaults: {
        altitude_m: 5000, mach: 0.35, mass_flow_air_kg_s: 12,
        compressor_pressure_ratio: 9, compressor_efficiency: 0.84,
        turbine_inlet_temperature_K: 1250, hp_turbine_efficiency: 0.88,
        power_turbine_efficiency: 0.88, combustor_efficiency: 0.99,
        combustor_pressure_loss_fraction: 0.05, mechanical_efficiency: 0.98,
        gearbox_efficiency: 0.985, propeller_diameter_m: 3.0, propeller_rpm: 1200,
        peak_propeller_efficiency: 0.86, advance_ratio_at_peak: 1.1,
        minimum_core_nozzle_temperature_K: 700, nozzle_efficiency: 0.92,
        inlet_pressure_recovery: 0.98, fuel_heating_value_J_kg: 43000000,
      },
      essential: ["altitude_m", "mach", "mass_flow_air_kg_s", "compressor_pressure_ratio", "turbine_inlet_temperature_K", "propeller_diameter_m"],
      fields: [
        { key: "altitude_m", label: "Altitude", unit: "m", step: 100 },
        { key: "mach", label: "Flight Mach", unit: "", step: 0.02 },
        { key: "mass_flow_air_kg_s", label: "Air mass flow", unit: "kg/s", step: 1 },
        { key: "compressor_pressure_ratio", label: "Compressor PR", unit: "", step: 0.5 },
        { key: "turbine_inlet_temperature_K", label: "Turbine inlet T", unit: "K", step: 10 },
        { key: "propeller_diameter_m", label: "Prop diameter", unit: "m", step: 0.1 },
        { key: "compressor_efficiency", label: "Compressor η", unit: "", step: 0.01 },
        { key: "hp_turbine_efficiency", label: "HPT η", unit: "", step: 0.01 },
        { key: "power_turbine_efficiency", label: "Power turbine η", unit: "", step: 0.01 },
        { key: "gearbox_efficiency", label: "Gearbox η", unit: "", step: 0.005 },
        { key: "propeller_rpm", label: "Prop RPM", unit: "rev/min", step: 50 },
        { key: "peak_propeller_efficiency", label: "Peak prop η", unit: "", step: 0.01 },
        { key: "advance_ratio_at_peak", label: "Peak advance ratio J*", unit: "", step: 0.1 },
        { key: "minimum_core_nozzle_temperature_K", label: "Min core nozzle T", unit: "K", step: 10 },
        { key: "nozzle_efficiency", label: "Nozzle η", unit: "", step: 0.01 },
        { key: "inlet_pressure_recovery", label: "Inlet recovery", unit: "", step: 0.01 },
      ],
      sweep: {
        parameters: [
          ["mach", "Flight Mach"],
          ["altitude_m", "Altitude"],
          ["compressor_pressure_ratio", "Compressor PR"],
          ["turbine_inlet_temperature_K", "Turbine inlet T"],
          ["propeller_rpm", "Propeller RPM"],
        ],
        parameter: "mach",
        values: "0, 0.2, 0.35, 0.5, 0.65",
      },
    },

    ramjet: {
      route: "/simulate/ramjet",
      sweepRoute: "/simulate/ramjet/sweep",
      label: "Ramjet",
      code: "PL-04",
      presetTypes: ["ramjet"],
      defaults: {
        altitude_m: 15000, mach: 2.2, mass_flow_air_kg_s: 25,
        inlet_pressure_recovery: 0.9, use_mil_spec_inlet_recovery: true,
        diffuser_efficiency: 0.95, combustor_inlet_mach: 0.25,
        combustor_exit_temperature_K: 1900, combustor_efficiency: 0.96,
        combustor_pressure_loss_fraction: 0.08, nozzle_efficiency: 0.94,
        nozzle_divergent_area_ratio: 1.0, fuel_heating_value_J_kg: 43000000,
      },
      essential: ["altitude_m", "mach", "mass_flow_air_kg_s", "combustor_exit_temperature_K", "combustor_inlet_mach"],
      fields: [
        { key: "altitude_m", label: "Altitude", unit: "m", step: 100 },
        { key: "mach", label: "Flight Mach", unit: "", step: 0.1 },
        { key: "mass_flow_air_kg_s", label: "Air mass flow", unit: "kg/s", step: 1 },
        { key: "combustor_exit_temperature_K", label: "Combustor exit T", unit: "K", step: 25 },
        { key: "combustor_inlet_mach", label: "Combustor inlet Mach", unit: "", step: 0.01 },
        { key: "use_mil_spec_inlet_recovery", label: "MIL-spec inlet recovery", type: "checkbox" },
        { key: "inlet_pressure_recovery", label: "Inlet recovery cap", unit: "", step: 0.01 },
        { key: "diffuser_efficiency", label: "Diffuser η", unit: "", step: 0.01 },
        { key: "combustor_efficiency", label: "Combustor η", unit: "", step: 0.01 },
        { key: "combustor_pressure_loss_fraction", label: "Combustor ΔP/P", unit: "", step: 0.01 },
        { key: "nozzle_efficiency", label: "Nozzle η", unit: "", step: 0.01 },
        { key: "nozzle_divergent_area_ratio", label: "Nozzle area ratio Aₑ/A*", unit: "", step: 0.1 },
      ],
      sweep: {
        parameters: [
          ["mach", "Flight Mach"],
          ["altitude_m", "Altitude"],
          ["combustor_exit_temperature_K", "Combustor exit T"],
          ["combustor_inlet_mach", "Combustor inlet Mach"],
          ["inlet_pressure_recovery", "Inlet recovery"],
        ],
        parameter: "mach",
        values: "1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5",
      },
    },

    scramjet: {
      route: "/simulate/scramjet",
      sweepRoute: "/simulate/scramjet/sweep",
      label: "Scramjet",
      code: "PL-05",
      presetTypes: ["scramjet"],
      defaults: {
        altitude_m: 22000, mach: 5, mass_flow_air_kg_s: 18,
        inlet_kinetic_energy_efficiency: 0.94, combustor_mach: 2.2,
        equivalence_ratio: 0.7, combustor_efficiency: 0.85,
        combustor_pressure_loss_fraction: 0.18, nozzle_efficiency: 0.93,
        nozzle_divergent_area_ratio: 6.0, fuel_heating_value_J_kg: 43000000,
        stoichiometric_fuel_air_ratio: 0.0685,
      },
      essential: ["altitude_m", "mach", "mass_flow_air_kg_s", "combustor_mach", "equivalence_ratio"],
      fields: [
        { key: "altitude_m", label: "Altitude", unit: "m", step: 250 },
        { key: "mach", label: "Flight Mach", unit: "", step: 0.5 },
        { key: "mass_flow_air_kg_s", label: "Air mass flow", unit: "kg/s", step: 1 },
        { key: "combustor_mach", label: "Combustor Mach", unit: "", step: 0.1 },
        { key: "equivalence_ratio", label: "Equivalence ratio φ", unit: "", step: 0.05 },
        { key: "inlet_kinetic_energy_efficiency", label: "Inlet η_KE", unit: "", step: 0.01 },
        { key: "combustor_efficiency", label: "Combustor η", unit: "", step: 0.01 },
        { key: "combustor_pressure_loss_fraction", label: "Combustor ΔP/P", unit: "", step: 0.01 },
        { key: "nozzle_efficiency", label: "Nozzle η", unit: "", step: 0.01 },
        { key: "nozzle_divergent_area_ratio", label: "Nozzle area ratio Aₑ/A*", unit: "", step: 0.5 },
        { key: "stoichiometric_fuel_air_ratio", label: "f_stoich", unit: "", step: 0.001 },
      ],
      sweep: {
        parameters: [
          ["mach", "Flight Mach"],
          ["equivalence_ratio", "Equivalence ratio"],
          ["altitude_m", "Altitude"],
          ["combustor_mach", "Combustor Mach"],
          ["inlet_kinetic_energy_efficiency", "Inlet η_KE"],
        ],
        parameter: "mach",
        values: "4, 5, 6, 7, 8, 9, 10",
      },
    },
  };

  const ENGINE_ORDER = ["turbojet", "turbofan", "turboprop", "ramjet", "scramjet"];

  /* ----------------------------------------------------------- *
   *  UNITS  (mirrors app.js — SI solver, display-only convert)  *
   * ----------------------------------------------------------- */
  const UNIT_KEY = "pl_units";
  let unitSystem = localStorage.getItem(UNIT_KEY) === "US" ? "US" : "SI";
  const UNIT_DEFS = {
    thrust: { si: "kN", us: "lbf", f: 224.808943 },
    tsfc: { si: "kg/kN·h", us: "lb/lbf·h", f: 0.00980665 },
    specthrust: { si: "N·s/kg", us: "lbf·s/lbm", f: 0.101971621 },
    temp: { si: "K", us: "°R", f: 1.8 },
    press: { si: "kPa", us: "psia", f: 0.145037738 },
    vel: { si: "m/s", us: "ft/s", f: 3.280839895 },
    power: { si: "kW", us: "hp", f: 1.34102209 },
  };
  const unitLabel = (k) => (unitSystem === "US" ? UNIT_DEFS[k].us : UNIT_DEFS[k].si);
  const unitConvert = (k, v) =>
    v == null || Number.isNaN(Number(v)) ? v : unitSystem === "US" ? Number(v) * UNIT_DEFS[k].f : Number(v);

  function numberFormat(v, digits = 2) {
    if (v == null || Number.isNaN(Number(v))) return "—";
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: digits });
  }
  const unum = (k, v, d = 1) => numberFormat(unitConvert(k, v), d);
  const uval = (k, v, d = 2) => `${unum(k, v, d)} ${unitLabel(k)}`;

  /* ----------------------------------------------------------- *
   *  STATE + DOM HELPERS                                        *
   * ----------------------------------------------------------- */
  const $ = (s) => document.querySelector(s);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  const state = {
    engine: "turbojet",
    working: {}, // per-engine input base (defaults, overlaid by preset)
    activePreset: {}, // per-engine active preset name
    lastResult: null,
    lastResultEngine: null,
    lastSweep: null,
    presets: [],
    activeTab: "design",
  };
  for (const k of ENGINE_ORDER) state.working[k] = { ...ENGINES[k].defaults };

  function setStatus(text, st) {
    $("#statusStrip").dataset.state = st || "idle";
    $("#statusText").textContent = text;
  }

  /* ----------------------------------------------------------- *
   *  NETWORK                                                    *
   * ----------------------------------------------------------- */
  function formatError(detail, fallback = "Request failed") {
    if (detail == null) return fallback;
    if (typeof detail === "string") return detail;
    const items = Array.isArray(detail) ? detail : [detail];
    return (
      items
        .map((d) => {
          if (typeof d === "string") return d;
          const where = Array.isArray(d?.loc) ? d.loc.filter((p) => p !== "body" && p !== "query").join(".") : "";
          const msg = d?.msg || d?.message || "invalid value";
          return where ? `${where}: ${msg}` : msg;
        })
        .filter(Boolean)
        .join("; ") || fallback
    );
  }
  async function postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : {};
    } catch {
      throw new Error(`Server error ${res.status}`);
    }
    if (!res.ok) throw new Error(formatError(payload?.detail, `Request failed (${res.status})`));
    return payload;
  }

  /* ----------------------------------------------------------- *
   *  ENGINE PICKER                                              *
   * ----------------------------------------------------------- */
  function buildEnginePicker() {
    const nav = $("#enginePicker");
    nav.replaceChildren();
    for (const key of ENGINE_ORDER) {
      const cfg = ENGINES[key];
      const btn = el("button", "m-engine" + (key === state.engine ? " is-active" : ""));
      btn.type = "button";
      btn.innerHTML =
        `<svg viewBox="0 0 64 22" fill="none" aria-hidden="true">${ICONS[key]}</svg>` +
        `<div class="m-engine-name">${cfg.label}</div>` +
        `<div class="m-engine-code">${cfg.code}</div>`;
      btn.addEventListener("click", () => selectEngine(key));
      nav.append(btn);
    }
  }

  function selectEngine(key) {
    if (key === state.engine) return;
    state.engine = key;
    buildEnginePicker();
    buildConcept();
    buildFields();
    buildPresets();
    buildSweepControls();
    // results belong to the previously run engine; reset to a clean slate
    showResultsEmpty();
    state.lastSweep = null;
    $("#sweepResult").hidden = true;
    switchTab("design");
    setStatus(`${ENGINES[key].label} ready`, "ok");
  }

  function buildConcept() {
    $("#conceptStrip").innerHTML =
      `<span class="m-concept-eyebrow">${ENGINES[state.engine].code} · ${ENGINES[state.engine].label}</span>` +
      CONCEPTS[state.engine];
    $("#designTitle").textContent = `${ENGINES[state.engine].label} design point`;
  }

  /* ----------------------------------------------------------- *
   *  FIELDS                                                     *
   * ----------------------------------------------------------- */
  function fieldNode(field) {
    const cfg = ENGINES[state.engine];
    const value = state.working[state.engine][field.key];

    if (field.type === "checkbox") {
      const wrap = el("label", "m-check");
      const lab = el("span", "m-field-label", field.label);
      const sw = el("span", "m-switch");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.id = `f_${field.key}`;
      input.checked = Boolean(value);
      const track = el("span", "m-track");
      sw.append(input, track);
      wrap.append(lab, sw);
      return wrap;
    }

    const wrap = el("label", "m-field");
    const lab = el("span", "m-field-label");
    lab.append(document.createTextNode(field.label));
    if (field.unit) lab.append(Object.assign(el("span", "m-unit"), { textContent: field.unit }));
    wrap.append(lab);

    if (field.type === "select") {
      const sel = document.createElement("div");
      sel.className = "m-select-wrap";
      const s = document.createElement("select");
      s.id = `f_${field.key}`;
      for (const [v, l] of field.options) {
        const o = document.createElement("option");
        o.value = v;
        o.textContent = l;
        if (String(v) === String(value)) o.selected = true;
        s.append(o);
      }
      sel.append(s);
      wrap.append(sel);
    } else {
      const input = document.createElement("input");
      input.type = "number";
      input.inputMode = "decimal";
      input.id = `f_${field.key}`;
      input.step = field.step != null ? field.step : "any";
      if (value != null) input.value = value;
      wrap.append(input);
    }
    return wrap;
  }

  function buildFields() {
    const cfg = ENGINES[state.engine];
    const essBox = $("#essentialFields");
    const advBox = $("#advancedFields");
    essBox.replaceChildren();
    advBox.replaceChildren();
    const essSet = new Set(cfg.essential);
    // essential, in declared essential order
    for (const k of cfg.essential) {
      const f = cfg.fields.find((x) => x.key === k);
      if (f) essBox.append(fieldNode(f));
    }
    // everything else → advanced
    for (const f of cfg.fields) {
      if (!essSet.has(f.key)) advBox.append(fieldNode(f));
    }
  }

  function readForm() {
    const cfg = ENGINES[state.engine];
    const body = { ...state.working[state.engine] };
    for (const f of cfg.fields) {
      const node = document.getElementById(`f_${f.key}`);
      if (!node) continue;
      if (f.type === "checkbox") {
        body[f.key] = node.checked;
      } else if (f.type === "select") {
        body[f.key] = node.value;
      } else {
        const raw = node.value.trim();
        if (raw === "") {
          if (f.nullable) body[f.key] = null;
          // else: keep the working-base default
        } else {
          body[f.key] = Number(raw);
        }
      }
    }
    return body;
  }

  /* ----------------------------------------------------------- *
   *  PRESETS                                                    *
   * ----------------------------------------------------------- */
  async function loadPresets() {
    try {
      const res = await fetch("/presets");
      if (!res.ok) return;
      const payload = await res.json();
      state.presets = payload.presets || [];
      buildPresets();
    } catch {
      /* presets are a nicety; defaults still work */
    }
  }

  function presetsForEngine() {
    const types = ENGINES[state.engine].presetTypes;
    return state.presets.filter((p) => types.includes(p.engine_type));
  }

  function buildPresets() {
    const box = $("#presetChips");
    box.replaceChildren();
    const list = presetsForEngine();
    if (!list.length) {
      box.append(el("span", "m-preset-empty", "Using built-in defaults for this family."));
      return;
    }
    for (const preset of list) {
      const chip = el("button", "m-preset" + (state.activePreset[state.engine] === preset.name ? " is-active" : ""));
      chip.type = "button";
      chip.textContent = preset.status && preset.status !== "available" ? `${preset.name} · ${preset.status}` : preset.name;
      chip.addEventListener("click", () => applyPreset(preset.name));
      box.append(chip);
    }
  }

  function applyPreset(name) {
    const preset = presetsForEngine().find((p) => p.name === name);
    if (!preset) return;
    state.activePreset[state.engine] = name;
    state.working[state.engine] = { ...ENGINES[state.engine].defaults, ...(preset.default_inputs || {}) };
    buildFields();
    buildPresets();
  }

  /* ----------------------------------------------------------- *
   *  RUN  +  RESULTS                                            *
   * ----------------------------------------------------------- */
  async function runSimulation() {
    const cfg = ENGINES[state.engine];
    const btn = $("#runButton");
    btn.disabled = true;
    btn.classList.add("is-busy");
    btn.textContent = "Solving…";
    setStatus(`Solving ${cfg.label}…`, "busy");
    try {
      const body = readForm();
      state.working[state.engine] = body; // remember last edited point
      const result = await postJson(cfg.route, body);
      state.lastResult = result;
      state.lastResultEngine = state.engine;
      renderResults(result);
      setStatus(`${cfg.label} solved`, "ok");
      switchTab("results");
    } catch (err) {
      setStatus(err.message || "Solve failed", "error");
      switchTab("results");
      showResultsEmpty(err.message || "The solver rejected these inputs.");
    } finally {
      btn.disabled = false;
      btn.classList.remove("is-busy");
      btn.textContent = "Run cycle";
    }
  }

  function showResultsEmpty(message) {
    $("#resultsBody").hidden = true;
    const empty = $("#resultsEmpty");
    empty.hidden = false;
    empty.querySelector("p").textContent =
      message || "Run a cycle to see thrust, efficiency and every station.";
  }

  function metricCard(label, num, unit, accent) {
    const card = el("div", "m-metric" + (accent ? ` accent-${accent}` : ""));
    card.append(el("div", "m-metric-label", label));
    const val = el("div", "m-metric-value");
    val.append(document.createTextNode(num));
    if (unit) val.append(Object.assign(el("span", "m-metric-unit"), { textContent: unit }));
    card.append(val);
    return card;
  }

  function renderResults(r) {
    $("#resultsEmpty").hidden = true;
    $("#resultsBody").hidden = false;

    // hero metric cards
    const cards = $("#metricCards");
    cards.replaceChildren(
      metricCard("Thrust", unum("thrust", r.thrust_N / 1000, 2), unitLabel("thrust"), "thrust"),
      metricCard("TSFC", unum("tsfc", r.TSFC_kg_per_kN_hr, 2), unitLabel("tsfc"), "tsfc"),
      metricCard("Specific thrust", unum("specthrust", r.specific_thrust_N_per_kg_s, 1), unitLabel("specthrust")),
      metricCard("Overall η", numberFormat(r.overall_efficiency_estimate * 100, 1), "%")
    );

    // secondary performance rows
    const rows = $("#secondaryRows");
    rows.replaceChildren();
    const add = (label, value) => {
      const row = el("div", "m-row");
      row.append(el("span", "m-row-label", label), el("span", "m-row-value", value));
      rows.append(row);
    };
    add("Thermal efficiency", `${numberFormat(r.thermal_efficiency_estimate * 100, 1)} %`);
    add("Propulsive efficiency", `${numberFormat(r.propulsive_efficiency_estimate * 100, 1)} %`);
    if (r.exit_velocity_m_s != null) add("Exit velocity", uval("vel", r.exit_velocity_m_s, 0));
    if (r.momentum_thrust_N != null) add("Momentum thrust", uval("thrust", r.momentum_thrust_N / 1000, 2));
    if (r.pressure_thrust_N != null) add("Pressure thrust", uval("thrust", r.pressure_thrust_N / 1000, 2));
    // engine-specific extras, rendered only when present
    const optThrust = [
      ["Core thrust", "core_thrust_N"],
      ["Bypass thrust", "bypass_thrust_N"],
      ["Third-stream thrust", "third_stream_thrust_N"],
      ["Propeller thrust", "propeller_thrust_N"],
      ["Residual jet thrust", "jet_thrust_N"],
    ];
    for (const [label, key] of optThrust) {
      if (r[key] != null) add(label, uval("thrust", r[key] / 1000, 2));
    }
    const optPower = [
      ["Shaft power", "shaft_power_kW"],
      ["Equivalent shaft power", "equivalent_shaft_power_kW"],
      ["Propeller power", "propeller_power_kW"],
    ];
    for (const [label, key] of optPower) {
      if (r[key] != null) add(label, uval("power", r[key], 0));
    }
    if (r.fuel_air_ratio != null) add("Fuel-air ratio", numberFormat(r.fuel_air_ratio, 4));
    if (r.fuel_mass_flow_kg_s != null) add("Fuel flow", `${numberFormat(r.fuel_mass_flow_kg_s, 3)} kg/s`);

    renderStationTable(r.station_table);
    drawStationChart();
    renderWarnings(r.warnings);
  }

  function stationList(table) {
    if (!table) return [];
    return Object.values(table).sort((a, b) => a.station - b.station);
  }

  function renderStationTable(table) {
    const stations = stationList(table);
    const head = $("#stationHead");
    const tHead = el("tr");
    [
      ["m-col-station", "Station"],
      ["", `T₀ ${unitLabel("temp")}`],
      ["", `P₀ ${unitLabel("press")}`],
      ["", "Mach"],
      ["", `V ${unitLabel("vel")}`],
    ].forEach(([cls, label]) => tHead.append(Object.assign(el("th", cls), { textContent: label })));
    head.replaceChildren(tHead);

    const body = $("#stationBody");
    body.replaceChildren();
    for (const s of stations) {
      const tr = el("tr");
      const name = el("td", "m-col-station");
      name.append(document.createTextNode(s.name || `Station ${s.station}`));
      tr.append(name);
      const cells = [
        unum("temp", s.stagnation_temperature_K, 0),
        unum("press", s.stagnation_pressure_Pa != null ? s.stagnation_pressure_Pa / 1000 : null, 1),
        s.mach != null ? numberFormat(s.mach, 2) : "—",
        s.velocity_m_s != null ? unum("vel", s.velocity_m_s, 0) : "—",
      ];
      for (const c of cells) tr.append(Object.assign(el("td", "m-col-num"), { textContent: c }));
      body.append(tr);
    }
  }

  function renderWarnings(warnings) {
    const box = $("#resultWarnings");
    box.replaceChildren();
    if (!Array.isArray(warnings)) return;
    for (const w of warnings) {
      if (!w) continue;
      box.append(el("div", "m-warn-item", typeof w === "string" ? w : w.message || String(w)));
    }
  }

  /* ----------------------------------------------------------- *
   *  CANVAS CHARTS                                              *
   * ----------------------------------------------------------- */
  const CHART = {
    temp: "#d97757",
    press: "#7ba7eb",
    thrust: "#f0883e",
    tsfc: "#7ba7eb",
    grid: "rgba(255,255,255,0.07)",
    axis: "rgba(244,244,245,0.40)",
    dim: "rgba(244,244,245,0.55)",
  };

  function scaleCanvas(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || canvas.parentElement.clientWidth || 320;
    const h = Number(canvas.getAttribute("height")) || 240;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w, h };
  }

  function lineSeries(ctx, pts, color, dash) {
    if (pts.length < 2) {
      if (pts.length) dot(ctx, pts[0][0], pts[0][1], color);
      return;
    }
    ctx.save();
    ctx.setLineDash(dash || []);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.8;
    ctx.lineJoin = "round";
    ctx.beginPath();
    pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.stroke();
    ctx.restore();
    for (const [x, y] of pts) dot(ctx, x, y, color);
  }
  function dot(ctx, x, y, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, 2.6, 0, Math.PI * 2);
    ctx.fill();
  }
  function legend(ctx, items, x, y) {
    ctx.font = "500 10px 'JetBrains Mono', monospace";
    ctx.textBaseline = "middle";
    let cx = x;
    for (const [label, color] of items) {
      ctx.fillStyle = color;
      ctx.fillRect(cx, y - 1, 12, 2);
      cx += 16;
      ctx.fillStyle = CHART.dim;
      ctx.textAlign = "left";
      ctx.fillText(label, cx, y);
      cx += ctx.measureText(label).width + 16;
    }
  }

  function drawStationChart() {
    const canvas = $("#stationCanvas");
    if (!canvas || canvas.clientWidth === 0) return;
    const r = state.lastResult;
    const { ctx, w, h } = scaleCanvas(canvas);
    ctx.clearRect(0, 0, w, h);
    const stations = stationList(r && r.station_table);
    const padL = 14, padR = 14, padT = 30, padB = 26;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;
    if (stations.length < 2) return;

    const T = stations.map((s) => unitConvert("temp", s.stagnation_temperature_K));
    const P = stations.map((s) => unitConvert("press", s.stagnation_pressure_Pa != null ? s.stagnation_pressure_Pa / 1000 : null));

    // gridlines
    ctx.strokeStyle = CHART.grid;
    ctx.lineWidth = 1;
    for (let i = 0; i <= 3; i++) {
      const y = padT + (plotH * i) / 3;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(w - padR, y);
      ctx.stroke();
    }

    const norm = (arr) => {
      const vals = arr.filter((v) => v != null && !Number.isNaN(v));
      const lo = Math.min(...vals), hi = Math.max(...vals);
      const span = hi - lo || 1;
      return { lo, hi, map: (v) => (v == null ? null : (v - lo) / span) };
    };
    const nT = norm(T), nP = norm(P);
    const xAt = (i) => padL + (plotW * i) / (stations.length - 1);
    const yAt = (f) => padT + plotH - plotH * f;

    const ptsT = stations.map((s, i) => [xAt(i), yAt(nT.map(T[i]))]);
    const ptsP = stations.map((s, i) => (nP.map(P[i]) == null ? null : [xAt(i), yAt(nP.map(P[i]))])).filter(Boolean);
    lineSeries(ctx, ptsP, CHART.press, [5, 4]);
    lineSeries(ctx, ptsT, CHART.temp);

    // x station numbers
    ctx.fillStyle = CHART.axis;
    ctx.font = "500 9px 'JetBrains Mono', monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (let i = 0; i < stations.length; i++) {
      ctx.fillText(String(stations[i].station), xAt(i), h - padB + 7);
    }

    legend(
      ctx,
      [
        [`T₀ ${numberFormat(nT.lo, 0)}–${numberFormat(nT.hi, 0)} ${unitLabel("temp")}`, CHART.temp],
        [`P₀ ${unitLabel("press")}`, CHART.press],
      ],
      padL,
      12
    );
  }

  function drawSweepChart() {
    const canvas = $("#sweepCanvas");
    if (!canvas || canvas.clientWidth === 0) return;
    const payload = state.lastSweep;
    const { ctx, w, h } = scaleCanvas(canvas);
    ctx.clearRect(0, 0, w, h);
    if (!payload) return;
    const cases = (payload.cases || []).filter((c) => c.success && c.output);
    const padL = 14, padR = 14, padT = 30, padB = 28;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;
    if (!cases.length) {
      ctx.fillStyle = CHART.dim;
      ctx.font = "500 12px 'Inter', system-ui";
      ctx.textAlign = "center";
      ctx.fillText("No successful sweep cases", w / 2, h / 2);
      return;
    }

    const xs = cases.map((c) => c.input_value);
    const thrust = cases.map((c) => unitConvert("thrust", c.output.thrust_kN != null ? c.output.thrust_kN : c.output.thrust_N / 1000));
    const tsfc = cases.map((c) => unitConvert("tsfc", c.output.TSFC_kg_per_kN_hr));

    ctx.strokeStyle = CHART.grid;
    ctx.lineWidth = 1;
    for (let i = 0; i <= 3; i++) {
      const y = padT + (plotH * i) / 3;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(w - padR, y);
      ctx.stroke();
    }

    const xLo = Math.min(...xs), xHi = Math.max(...xs);
    const xSpan = xHi - xLo || 1;
    const xAt = (v) => padL + (plotW * (v - xLo)) / xSpan;
    const maxT = Math.max(...thrust) || 1;
    const maxF = Math.max(...tsfc) || 1;
    const yAt = (v, max) => padT + plotH - (plotH * v) / max;

    const ptsT = xs.map((v, i) => [xAt(v), yAt(thrust[i], maxT)]);
    const ptsF = xs.map((v, i) => [xAt(v), yAt(tsfc[i], maxF)]);
    lineSeries(ctx, ptsF, CHART.tsfc, [5, 4]);
    lineSeries(ctx, ptsT, CHART.thrust);

    // x ticks: lo, mid, hi
    ctx.fillStyle = CHART.axis;
    ctx.font = "500 9px 'JetBrains Mono', monospace";
    ctx.textBaseline = "top";
    [
      [xLo, "left"],
      [(xLo + xHi) / 2, "center"],
      [xHi, "right"],
    ].forEach(([v, align]) => {
      ctx.textAlign = align;
      const x = align === "left" ? padL : align === "right" ? w - padR : w / 2;
      ctx.fillText(numberFormat(v, 2), x, h - padB + 8);
    });

    legend(
      ctx,
      [
        [`Thrust ${unitLabel("thrust")}`, CHART.thrust],
        [`TSFC ${unitLabel("tsfc")}`, CHART.tsfc],
      ],
      padL,
      12
    );
  }

  /* ----------------------------------------------------------- *
   *  SWEEP                                                      *
   * ----------------------------------------------------------- */
  function buildSweepControls() {
    const cfg = ENGINES[state.engine];
    const sel = $("#sweepParameter");
    sel.replaceChildren();
    for (const [v, l] of cfg.sweep.parameters) {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = l;
      if (v === cfg.sweep.parameter) o.selected = true;
      sel.append(o);
    }
    $("#sweepValues").value = cfg.sweep.values;
  }

  async function runSweep() {
    const cfg = ENGINES[state.engine];
    const btn = $("#runSweepButton");
    const values = $("#sweepValues")
      .value.split(",")
      .map((v) => Number(v.trim()))
      .filter((v) => !Number.isNaN(v));
    if (!values.length) {
      setStatus("Enter at least one sweep value", "error");
      return;
    }
    btn.disabled = true;
    btn.classList.add("is-busy");
    btn.textContent = "Sweeping…";
    setStatus(`Sweeping ${cfg.label}…`, "busy");
    try {
      const payload = await postJson(cfg.sweepRoute, {
        base_input: readForm(),
        sweep_parameter: $("#sweepParameter").value,
        values,
      });
      state.lastSweep = payload;
      $("#sweepResult").hidden = false;
      const sum = payload.summary || {};
      $("#sweepSummary").textContent =
        `${sum.successful_cases ?? 0} ok · ${sum.failed_cases ?? 0} failed` +
        (sum.max_thrust_N != null ? ` · peak thrust ${uval("thrust", sum.max_thrust_N / 1000, 1)}` : "") +
        (sum.min_TSFC_kg_per_kN_hr != null ? ` · min TSFC ${uval("tsfc", sum.min_TSFC_kg_per_kN_hr, 2)}` : "");
      drawSweepChart();
      setStatus(`${cfg.label} sweep done`, "ok");
    } catch (err) {
      setStatus(err.message || "Sweep failed", "error");
    } finally {
      btn.disabled = false;
      btn.classList.remove("is-busy");
      btn.textContent = "Run sweep";
    }
  }

  /* ----------------------------------------------------------- *
   *  TABS + MENU + UNITS                                        *
   * ----------------------------------------------------------- */
  function switchTab(tab) {
    state.activeTab = tab;
    document.querySelectorAll(".m-tab").forEach((t) => {
      const on = t.dataset.tab === tab;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    document.querySelectorAll(".m-panel").forEach((p) => {
      const on = p.dataset.panel === tab;
      p.classList.toggle("is-active", on);
      p.hidden = !on;
    });
    // charts can only measure width once their panel is visible
    if (tab === "results" && state.lastResult) requestAnimationFrame(drawStationChart);
    if (tab === "sweep" && state.lastSweep) requestAnimationFrame(drawSweepChart);
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function toggleMenu(open) {
    const sheet = $("#menuSheet");
    const backdrop = $("#sheetBackdrop");
    const btn = $("#menuToggle");
    if (open) {
      backdrop.hidden = false;
      requestAnimationFrame(() => sheet.classList.add("is-open"));
    } else {
      sheet.classList.remove("is-open");
      setTimeout(() => (backdrop.hidden = true), 320);
    }
    sheet.setAttribute("aria-hidden", open ? "false" : "true");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function setUnits(sys) {
    unitSystem = sys === "US" ? "US" : "SI";
    localStorage.setItem(UNIT_KEY, unitSystem);
    $("#unitToggle").textContent = unitSystem;
    // re-render cached result + sweep in the new system
    if (state.lastResult) renderResults(state.lastResult);
    if (state.lastSweep) {
      const sum = state.lastSweep.summary || {};
      $("#sweepSummary").textContent =
        `${sum.successful_cases ?? 0} ok · ${sum.failed_cases ?? 0} failed` +
        (sum.max_thrust_N != null ? ` · peak thrust ${uval("thrust", sum.max_thrust_N / 1000, 1)}` : "") +
        (sum.min_TSFC_kg_per_kN_hr != null ? ` · min TSFC ${uval("tsfc", sum.min_TSFC_kg_per_kN_hr, 2)}` : "");
      drawSweepChart();
    }
  }

  /* ----------------------------------------------------------- *
   *  BOOT                                                       *
   * ----------------------------------------------------------- */
  function bindEvents() {
    $("#runButton").addEventListener("click", runSimulation);
    $("#runSweepButton").addEventListener("click", runSweep);
    document.querySelectorAll(".m-tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));
    $("#unitToggle").addEventListener("click", () => setUnits(unitSystem === "US" ? "SI" : "US"));
    $("#menuToggle").addEventListener("click", () => toggleMenu($("#menuSheet").getAttribute("aria-hidden") === "true"));
    $("#sheetClose").addEventListener("click", () => toggleMenu(false));
    $("#sheetBackdrop").addEventListener("click", () => toggleMenu(false));
    let rt;
    window.addEventListener("resize", () => {
      clearTimeout(rt);
      rt = setTimeout(() => {
        if (state.activeTab === "results" && state.lastResult) drawStationChart();
        if (state.activeTab === "sweep" && state.lastSweep) drawSweepChart();
      }, 150);
    });
  }

  async function pingApi() {
    try {
      const res = await fetch("/api");
      if (res.ok) setStatus(`Solver linked · ${ENGINES[state.engine].label}`, "ok");
      else setStatus("Solver unreachable", "error");
    } catch {
      setStatus("Solver unreachable", "error");
    }
  }

  function init() {
    $("#unitToggle").textContent = unitSystem;
    buildEnginePicker();
    buildConcept();
    buildFields();
    buildPresets();
    buildSweepControls();
    bindEvents();
    pingApi();
    loadPresets();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

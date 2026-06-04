/* =============================================================
   DAS LABS · PropulsionLab, Console
   v3.0  Restrained aerospace product.
   All backend solver / sweep / compare / PDF / profile flows
   preserved verbatim. No boot sequence, no particles, no mission
   clock, no looping engine animation. Calm motion, hairline
   borders, muted typographic chart palette.
   ============================================================= */

/* ------------------------------------------------------------ *
 *  1. DEFAULT INPUT & ENGINE METADATA                           *
 * ------------------------------------------------------------ */

const defaultInput = {
  engine_variant: "turbojet",
  altitude_m: 10000,
  mach: 0.8,
  mass_flow_air_kg_s: 50,
  inlet_capture_area_m2: null,
  use_inlet_area_mass_flow: false,
  compressor_pressure_ratio: 12,
  compressor_efficiency: 0.86,
  turbine_inlet_temperature_K: 1400,
  turbine_efficiency: 0.88,
  combustor_efficiency: 0.99,
  combustor_pressure_loss_fraction: 0.05,
  mechanical_efficiency: 0.99,
  nozzle_efficiency: 0.95,
  inlet_pressure_recovery: 0.98,
  fuel_heating_value_J_kg: 43000000,
  nozzle_exit_area_m2: null,
  nozzle_throat_area_m2: null,
  include_pressure_thrust: true,
  afterburner_exit_temperature_K: null,
  afterburner_efficiency: 0.95,
  afterburner_pressure_loss_fraction: 0.06,
};

const engineLabels = {
  turbojet: "Turbojet",
  turbofan: "Turbofan",
  turboprop: "Turboprop",
  ramjet: "Ramjet",
  scramjet: "Scramjet",
};

/*
 * Each engine field is [key, label, unit, opts] where opts is optional and may
 * contain { type: "select", options: [[value, label], ...] } or
 * { type: "checkbox" }. Default type is a numeric input.
 */
const advancedEngineConfigs = {
  turbofan: {
    route: "/simulate/turbofan",
    sweepRoute: "/simulate/turbofan/sweep",
    title: "Turbofan parameters",
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
      fuel_heating_value_J_kg: 43000000,
      use_afterburner: false,
      afterburner_exit_temperature_K: 2000,
      afterburner_efficiency: 0.94, afterburner_pressure_loss_fraction: 0.08,
      mixer_pressure_loss_fraction: 0.02,
      third_stream: false, variable_cycle_mode: "high_efficiency",
      third_stream_ratio: 0.6, third_stream_pressure_ratio: 1.3,
      third_stream_nozzle_efficiency: 0.94,
    },
    fields: [
      ["nozzle_configuration", "Nozzle config", "", { type: "select",
        options: [["separate", "Separate flow"], ["mixed", "Mixed flow"]] }],
      ["third_stream", "3-stream (variable cycle)", "", { type: "checkbox" }],
      ["variable_cycle_mode", "Cycle mode", "", { type: "select",
        options: [["high_efficiency", "High efficiency (open)"], ["high_thrust", "High thrust (closed)"]] }],
      ["third_stream_ratio", "Third-stream ratio", ""],
      ["third_stream_pressure_ratio", "Third-stream PR", ""],
      ["altitude_m", "Altitude", "m"],
      ["mach", "Mach", ""],
      ["total_mass_flow_air_kg_s", "Total ṁ air", "kg/s"],
      ["bypass_ratio", "Bypass ratio", ""],
      ["fan_pressure_ratio", "Fan PR", ""],
      ["fan_efficiency", "Fan η", ""],
      ["core_compressor_pressure_ratio", "Core HPC PR", ""],
      ["compressor_efficiency", "HPC η", ""],
      ["turbine_inlet_temperature_K", "Turbine inlet T", "K"],
      ["hp_turbine_efficiency", "HPT η", ""],
      ["lp_turbine_efficiency", "LPT η", ""],
      ["combustor_efficiency", "Combustor η", ""],
      ["combustor_pressure_loss_fraction", "Combustor ΔP/P", ""],
      ["core_nozzle_efficiency", "Core nozzle η", ""],
      ["bypass_nozzle_efficiency", "Bypass nozzle η", ""],
      ["mixer_pressure_loss_fraction", "Mixer ΔP/P (mixed only)", ""],
      ["inlet_pressure_recovery", "Inlet recovery", ""],
      ["use_afterburner", "Use afterburner", "", { type: "checkbox" }],
      ["afterburner_exit_temperature_K", "AB exit T", "K"],
      ["afterburner_efficiency", "AB η", ""],
      ["afterburner_pressure_loss_fraction", "AB ΔP/P", ""],
    ],
    sweepParameters: [
      ["bypass_ratio", "Bypass ratio"],
      ["fan_pressure_ratio", "Fan PR"],
      ["core_compressor_pressure_ratio", "Core HPC PR"],
      ["turbine_inlet_temperature_K", "Turbine inlet T"],
      ["mach", "Mach"],
      ["altitude_m", "Altitude"],
    ],
    sweepDefault: { parameter: "bypass_ratio", values: "1, 3, 5, 8, 11" },
  },
  turboprop: {
    route: "/simulate/turboprop",
    sweepRoute: "/simulate/turboprop/sweep",
    title: "Turboprop parameters",
    defaults: {
      altitude_m: 5000, mach: 0.35, mass_flow_air_kg_s: 12,
      compressor_pressure_ratio: 9, compressor_efficiency: 0.84,
      turbine_inlet_temperature_K: 1250,
      hp_turbine_efficiency: 0.88, power_turbine_efficiency: 0.88,
      combustor_efficiency: 0.99, combustor_pressure_loss_fraction: 0.05,
      mechanical_efficiency: 0.98, gearbox_efficiency: 0.985,
      propeller_diameter_m: 3.0, propeller_rpm: 1200,
      peak_propeller_efficiency: 0.86, advance_ratio_at_peak: 1.1,
      minimum_core_nozzle_temperature_K: 700, nozzle_efficiency: 0.92,
      inlet_pressure_recovery: 0.98, fuel_heating_value_J_kg: 43000000,
    },
    fields: [
      ["altitude_m", "Altitude", "m"],
      ["mach", "Mach", ""],
      ["mass_flow_air_kg_s", "Air mass flow", "kg/s"],
      ["compressor_pressure_ratio", "Compressor PR", ""],
      ["compressor_efficiency", "Compressor η", ""],
      ["turbine_inlet_temperature_K", "Turbine inlet T", "K"],
      ["hp_turbine_efficiency", "HPT η", ""],
      ["power_turbine_efficiency", "Power turbine η", ""],
      ["gearbox_efficiency", "Gearbox η", ""],
      ["propeller_diameter_m", "Prop diameter", "m"],
      ["propeller_rpm", "Prop RPM", "rev/min"],
      ["peak_propeller_efficiency", "Peak prop η", ""],
      ["advance_ratio_at_peak", "Peak advance ratio J*", ""],
      ["minimum_core_nozzle_temperature_K", "Min core nozzle T", "K"],
      ["nozzle_efficiency", "Nozzle η", ""],
      ["inlet_pressure_recovery", "Inlet recovery", ""],
    ],
    sweepParameters: [
      ["mach", "Mach"],
      ["altitude_m", "Altitude"],
      ["compressor_pressure_ratio", "Compressor PR"],
      ["turbine_inlet_temperature_K", "Turbine inlet T"],
      ["propeller_rpm", "Propeller RPM"],
    ],
    sweepDefault: { parameter: "mach", values: "0, 0.2, 0.35, 0.5, 0.65" },
  },
  ramjet: {
    route: "/simulate/ramjet",
    sweepRoute: "/simulate/ramjet/sweep",
    title: "Ramjet parameters",
    defaults: {
      altitude_m: 15000, mach: 2.2, mass_flow_air_kg_s: 25,
      inlet_pressure_recovery: 0.9, use_mil_spec_inlet_recovery: true,
      diffuser_efficiency: 0.95, combustor_inlet_mach: 0.25,
      combustor_exit_temperature_K: 1900, combustor_efficiency: 0.96,
      combustor_pressure_loss_fraction: 0.08, nozzle_efficiency: 0.94,
      nozzle_divergent_area_ratio: 1.0,
      fuel_heating_value_J_kg: 43000000,
    },
    fields: [
      ["altitude_m", "Altitude", "m"],
      ["mach", "Mach", ""],
      ["mass_flow_air_kg_s", "Air mass flow", "kg/s"],
      ["use_mil_spec_inlet_recovery", "MIL-spec inlet recovery", "", { type: "checkbox" }],
      ["inlet_pressure_recovery", "Inlet recovery cap", ""],
      ["diffuser_efficiency", "Diffuser η", ""],
      ["combustor_inlet_mach", "Combustor inlet Mach", ""],
      ["combustor_exit_temperature_K", "Combustor exit T", "K"],
      ["combustor_efficiency", "Combustor η", ""],
      ["combustor_pressure_loss_fraction", "Combustor ΔP/P", ""],
      ["nozzle_efficiency", "Nozzle η", ""],
      ["nozzle_divergent_area_ratio", "Nozzle area ratio Aₑ/A*", ""],
    ],
    sweepParameters: [
      ["mach", "Mach"],
      ["altitude_m", "Altitude"],
      ["combustor_exit_temperature_K", "Combustor exit T"],
      ["combustor_inlet_mach", "Combustor inlet Mach"],
      ["inlet_pressure_recovery", "Inlet recovery"],
    ],
    sweepDefault: { parameter: "mach", values: "1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5" },
  },
  scramjet: {
    route: "/simulate/scramjet",
    sweepRoute: "/simulate/scramjet/sweep",
    title: "Scramjet parameters",
    defaults: {
      altitude_m: 22000, mach: 5, mass_flow_air_kg_s: 18,
      inlet_kinetic_energy_efficiency: 0.94, combustor_mach: 2.2,
      equivalence_ratio: 0.7, combustor_efficiency: 0.85,
      combustor_pressure_loss_fraction: 0.18, nozzle_efficiency: 0.93,
      nozzle_divergent_area_ratio: 6.0,
      fuel_heating_value_J_kg: 43000000,
      stoichiometric_fuel_air_ratio: 0.0685,
    },
    fields: [
      ["altitude_m", "Altitude", "m"],
      ["mach", "Mach", ""],
      ["mass_flow_air_kg_s", "Air mass flow", "kg/s"],
      ["inlet_kinetic_energy_efficiency", "Inlet η_KE", ""],
      ["combustor_mach", "Combustor Mach", ""],
      ["equivalence_ratio", "Equivalence ratio φ", ""],
      ["combustor_efficiency", "Combustor η", ""],
      ["combustor_pressure_loss_fraction", "Combustor ΔP/P", ""],
      ["nozzle_efficiency", "Nozzle η", ""],
      ["nozzle_divergent_area_ratio", "Nozzle area ratio Aₑ/A*", ""],
      ["stoichiometric_fuel_air_ratio", "f_stoich", ""],
    ],
    sweepParameters: [
      ["mach", "Mach"],
      ["equivalence_ratio", "Equivalence ratio"],
      ["altitude_m", "Altitude"],
      ["combustor_mach", "Combustor Mach"],
      ["inlet_kinetic_energy_efficiency", "Inlet η_KE"],
    ],
    sweepDefault: { parameter: "mach", values: "4, 5, 6, 7, 8, 9, 10" },
  },
};

/* ------------------------------------------------------------ *
 *  2. CACHED DOM REFERENCES                                     *
 * ------------------------------------------------------------ */

const $ = (sel) => document.querySelector(sel);

const form = $("#simulationForm");
const apiStatus = $("#apiStatus");
const stationTableBody = $("#stationTableBody");
const warningsBox = $("#warnings");
const stationCanvas = $("#stationCanvas");
const engineViewerCanvas = $("#engineViewerCanvas");
const stationInspector = $("#stationInspector");
const nozzlePanel = $("#nozzlePanel");
const advancedEngineForm = $("#advancedEngineForm");
const advancedInputGrid = $("#advancedInputGrid");
const advancedStationCanvas = $("#advancedStationCanvas");
const advancedStationTableBody = $("#advancedStationTableBody");
const advancedWarningsBox = $("#advancedWarnings");
const sweepCanvas = $("#sweepCanvas");
const compareCanvas = $("#compareCanvas");
const presetSelect = $("#presetSelect");
const customProfileSelect = $("#customProfileSelect");
const profileNameInput = $("#profileNameInput");

const profileStorageKey = "propulsionLab.customJetProfiles.v1";

let selectedEngine = "turbojet";
let currentPresetInput = { ...defaultInput };
let presetCatalog = [];
let lastResult = null;
let lastSweepPayload = null;
let activeStation = null;
let engineViewerHitRegions = [];

/* ------------------------------------------------------------ *
 *  3. RESTRAINED COLOR PALETTE                                  *
 * ------------------------------------------------------------ */

const palette = {
  grid:       "rgba(255, 255, 255, 0.06)",
  gridStrong: "rgba(255, 255, 255, 0.10)",
  hairline:   "rgba(255, 255, 255, 0.18)",
  text:       "rgba(244, 244, 245, 0.62)",
  textDim:    "rgba(244, 244, 245, 0.42)",
  ink:        "#f4f4f5",
  surface:    "#0d0e11",
  surface2:   "#131418",

  // chart series, muted, premium
  thrust:      "#f4f4f5",
  tsfc:        "#d4d4d8",
  temperature: "#d97757",
  pressure:    "#7ba7eb",
  efficiency:  "#94a3b8",
  prop:        "#a1a1aa",
  overall:     "#71717a",
  accent:      "#7ba7eb",
};

const thermoReference = {
  cpAir: 1004,
  cpGas: 1150,
  rAir: 287,
  temperatureK: 288.15,
  pressurePa: 101325,
};

/* ------------------------------------------------------------ *
 *  4. UTILITIES                                                 *
 * ------------------------------------------------------------ */

function numberFormat(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return ", ";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
}

/* ------------------------------------------------------------ *
 *  UNIT SYSTEM (SI / US customary)                              *
 * ------------------------------------------------------------ *
 * The solver and API are SI throughout; this layer only converts what is
 * *displayed*. The choice is persisted, and toggling re-renders from the cached
 * lastResult (no re-fetch). Temperatures use Rankine, not Fahrenheit, so they
 * stay absolute and consistent with psia, the way US cycle analysis is taught. */
const UNIT_KEY = "pl_units";
let unitSystem = localStorage.getItem(UNIT_KEY) === "US" ? "US" : "SI";

const UNIT_DEFS = {
  thrust: { si: "kN", us: "lbf", f: 224.808943 },          // from kN
  tsfc: { si: "kg/kN·h", us: "lb/lbf·h", f: 0.00980665 },  // from kg/(kN·h)
  specthrust: { si: "N·s/kg", us: "lbf·s/lbm", f: 0.101971621 }, // from N/(kg/s)
  temp: { si: "K", us: "°R", f: 1.8 },                     // from K
  press: { si: "kPa", us: "psia", f: 0.145037738 },        // from kPa
  vel: { si: "m/s", us: "ft/s", f: 3.280839895 },          // from m/s
  flow: { si: "kg/s", us: "lb/s", f: 2.204622622 },        // from kg/s
  area: { si: "m²", us: "ft²", f: 10.76391042 },           // from m²
  len: { si: "m", us: "ft", f: 3.280839895 },              // from m
  power: { si: "kW", us: "hp", f: 1.34102209 },            // from kW
  bsfc: { si: "kg/kW·h", us: "lb/hp·h", f: 1.643988 },     // from kg/(kW·h)
};

function unitLabel(kind) {
  const d = UNIT_DEFS[kind];
  return unitSystem === "US" ? d.us : d.si;
}
function unitConvert(kind, value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return value;
  return unitSystem === "US" ? Number(value) * UNIT_DEFS[kind].f : Number(value);
}
/** "value unit" string in the active system (label travels with the number). */
function uval(kind, value, digits = 2) {
  return `${numberFormat(unitConvert(kind, value), digits)} ${unitLabel(kind)}`;
}
/** Number only, for tables whose column header already carries the unit. */
function unum(kind, value, digits = 1) {
  return numberFormat(unitConvert(kind, value), digits);
}
/** Rewrite every unit-bearing column header span to the active system. */
function updateStationHeaders() {
  document.querySelectorAll("[data-u]").forEach((el) => {
    el.textContent = `[${unitLabel(el.dataset.u)}]`;
  });
}
/** Re-render the cached result and headers when the unit system changes. */
function rerenderUnits() {
  updateStationHeaders();
  if (!lastResult) return;
  if (selectedEngine === "turbojet") {
    updateMetrics(lastResult);
    updateNozzlePanel(lastResult);
    updateStationTable(lastResult.station_table);
  } else {
    updateAdvancedMetrics(lastResult);
    if (typeof advancedStationTableBody !== "undefined" && advancedStationTableBody) {
      fillStationTable(advancedStationTableBody, lastResult.station_table);
    }
  }
  updateStationInspector();
  if (typeof lastSensitivity !== "undefined" && lastSensitivity) drawTornado(lastSensitivity);
  if (typeof lastTransient !== "undefined" && lastTransient) drawTransient(lastTransient);
}
function setUnitSystem(system) {
  unitSystem = system === "US" ? "US" : "SI";
  localStorage.setItem(UNIT_KEY, unitSystem);
  const btn = document.getElementById("unitToggle");
  if (btn) btn.textContent = `Units: ${unitSystem}`;
  rerenderUnits();
}
function initUnitToggle() {
  const btn = document.getElementById("unitToggle");
  updateStationHeaders();
  if (!btn) return;
  btn.textContent = `Units: ${unitSystem}`;
  btn.addEventListener("click", () =>
    setUnitSystem(unitSystem === "US" ? "SI" : "US"));
}

function setStatus(text, className) {
  apiStatus.textContent = text;
  apiStatus.className = `status-pill ${className || ""}`;
}

function canvasScale(canvas) {
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const fallbackWidth = canvas.parentElement?.clientWidth || Number(canvas.getAttribute("width")) || 520;
  const fallbackHeight = Number(canvas.getAttribute("height")) || 260;
  const width = rect.width || fallbackWidth;
  const height = rect.height || fallbackHeight;
  canvas.width = Math.max(1, Math.round(width * ratio));
  canvas.height = Math.max(1, Math.round(height * ratio));
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { context: ctx, width, height };
}

function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

/* FastAPI returns request-validation failures as an ARRAY of error objects
 * under `detail` (Pydantic), while the solver's own 400s return a plain
 * string. Passing the array straight into `new Error(...)` stringifies it to
 * "[object Object]", so normalise either shape into a readable sentence. */
function formatRequestError(detail, fallback = "Request failed") {
  if (detail === null || detail === undefined) return fallback;
  if (typeof detail === "string") return detail;
  const items = Array.isArray(detail) ? detail : [detail];
  const parts = items.map((d) => {
    if (typeof d === "string") return d;
    const where = Array.isArray(d?.loc)
      ? d.loc.filter((p) => p !== "body" && p !== "query").join(".")
      : "";
    const msg = d?.msg || d?.message || "invalid value";
    return where ? `${where}: ${msg}` : msg;
  });
  return parts.filter(Boolean).join("; ") || fallback;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  // Read as text first: an unexpected 5xx returns plain text, not JSON, and
  // calling response.json() on it throws a confusing "Unexpected token" error.
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(
      response.ok
        ? "The server returned an unreadable response."
        : `Server error ${response.status}. Please adjust the inputs and try again.`,
    );
  }
  if (!response.ok) throw new Error(formatRequestError(payload.detail));
  return payload;
}

/* ------------------------------------------------------------ *
 *  5. CALM HERO STAT COUNTERS                                   *
 * ------------------------------------------------------------ */

function animateHeroCounters() {
  document.querySelectorAll("[data-counter]").forEach((node) => {
    const target = Number(node.dataset.counter || 0);
    if (!Number.isFinite(target)) return;
    const unitNode = node.querySelector(".hero-stat-unit");
    const unitMarkup = unitNode ? unitNode.outerHTML : "";
    const start = performance.now();
    const duration = 900;
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const value = Math.round(easeOutCubic(t) * target);
      node.innerHTML = `${value}${unitMarkup}`;
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

/* ------------------------------------------------------------ *
 *  6. METRIC COUNT-UP (subtle)                                  *
 * ------------------------------------------------------------ */

const metricFromValue = new WeakMap();

function animateMetric(node, finalText, finalNumber) {
  if (!node) return;
  if (finalNumber === null || finalNumber === undefined || Number.isNaN(finalNumber)) {
    node.textContent = finalText;
    metricFromValue.delete(node);
    return;
  }
  const prev = metricFromValue.get(node);
  const start = (prev === undefined || Number.isNaN(prev)) ? finalNumber * 0.7 : prev;
  metricFromValue.set(node, finalNumber);
  const t0 = performance.now();
  const duration = 340;
  const formatter = (v) =>
    finalText.replace(/[\d.,−-]+/, () => numberFormat(v, finalText.includes(".") ? 2 : 1));
  const step = (now) => {
    const t = Math.min(1, (now - t0) / duration);
    const v = start + (finalNumber - start) * easeOutCubic(t);
    node.textContent = formatter(v);
    if (t < 1) requestAnimationFrame(step);
    else node.textContent = finalText;
  };
  requestAnimationFrame(step);
}

/* ------------------------------------------------------------ *
 *  7. FORM I/O                                                  *
 * ------------------------------------------------------------ */

function populateForm(inputValues = currentPresetInput) {
  for (const [key, value] of Object.entries({ ...defaultInput, ...inputValues })) {
    const field = form.elements.namedItem(key);
    if (!field) continue;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else if (field.tagName === "SELECT") field.value = value ?? "";
    else if (value !== null) field.value = value;
    else field.value = "";
  }
}

function readFormInput() {
  const data = { ...defaultInput };
  for (const key of Object.keys(defaultInput)) {
    const field = form.elements.namedItem(key);
    if (!field) continue;
    if (field.type === "checkbox") data[key] = field.checked;
    else if (field.tagName === "SELECT") data[key] = field.value;
    else if (field.value !== "") data[key] = Number(field.value);
    else if (
      key === "afterburner_exit_temperature_K" ||
      key === "nozzle_exit_area_m2" ||
      key === "nozzle_throat_area_m2" ||
      key === "inlet_capture_area_m2"
    ) {
      data[key] = null;
    }
  }
  return data;
}

/* ------------------------------------------------------------ *
 *  7a. GEOMETRIC-INPUT VALIDATION                              *
 *  The capture- and nozzle-area fields are optional, but once a *
 *  value is entered it has to be a positive, physically sensible*
 *  area. Without this the form quietly forwards a NaN (which    *
 *  JSON turns into null, so the area is silently dropped) or an *
 *  absurd magnitude, and the solver either ignores it or hands  *
 *  back non-physical thrust. NaN / <=0 block the run; an        *
 *  implausibly large area runs but raises a labelled caution.   *
 * ------------------------------------------------------------ */

const AREA_FIELDS = {
  inlet_capture_area_m2: { label: "Inlet capture area", typicalMax: 25 },
  nozzle_exit_area_m2: { label: "Nozzle exit area", typicalMax: 25 },
  nozzle_throat_area_m2: { label: "Nozzle throat area", typicalMax: 25 },
};

function collectGeometryProblems(data) {
  const errors = [];
  const cautions = [];
  for (const [key, meta] of Object.entries(AREA_FIELDS)) {
    if (!(key in data)) continue;
    const v = data[key];
    if (v === null || v === undefined || v === "") continue; // blank = auto-estimate
    if (!Number.isFinite(v)) {
      errors.push(`CRITICAL: ${meta.label} must be a number in m².`);
    } else if (v <= 0) {
      errors.push(`CRITICAL: ${meta.label} must be greater than 0 m².`);
    } else if (v > meta.typicalMax) {
      cautions.push(
        `CAUTION: ${meta.label} of ${numberFormat(v, 3)} m² is far larger ` +
          "than any real engine; treat the result as non-physical.",
      );
    }
  }
  if (data.use_inlet_area_mass_flow) {
    const a = data.inlet_capture_area_m2;
    if (!(Number.isFinite(a) && a > 0)) {
      errors.push(
        "CRITICAL: Inlet capture area must be positive to estimate mass flow from inlet area.",
      );
    }
  }
  return { errors, cautions };
}

/* ------------------------------------------------------------ *
 *  7b. SHAREABLE URL STATE                                      *
 *  Encode the current engine + input deck into a URL hash so a
 *  cycle is fully reproducible from a link. base64url of JSON;
 *  Unicode-safe. Used by the "Share link" buttons and read on
 *  page load to restore a shared scenario.
 * ------------------------------------------------------------ */

const SHARE_STATE_VERSION = 1;

function buildShareState() {
  const state = { v: SHARE_STATE_VERSION, e: selectedEngine, tj: readFormInput() };
  if (selectedEngine !== "turbojet") state.adv = readAdvancedInput();
  return state;
}

function encodeShareState(state) {
  const json = JSON.stringify(state);
  // Unicode-safe base64url.
  return btoa(unescape(encodeURIComponent(json)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function decodeShareState(token) {
  try {
    let b64 = token.replace(/-/g, "+").replace(/_/g, "/");
    // Restore base64 padding stripped during encode.
    while (b64.length % 4) b64 += "=";
    const json = decodeURIComponent(escape(atob(b64)));
    const state = JSON.parse(json);
    return state && typeof state === "object" ? state : null;
  } catch {
    return null;
  }
}

function shareableUrl() {
  return `${location.origin}${location.pathname}#s=${encodeShareState(buildShareState())}`;
}

function readSharedStateFromUrl() {
  const match = location.hash.match(/(?:^#|&)s=([^&]+)/);
  return match ? decodeShareState(match[1]) : null;
}

function flashButtonLabel(button, text, ms = 1500) {
  if (!button) return;
  const original = button.dataset.label || button.textContent;
  button.dataset.label = original;
  button.textContent = text;
  button.disabled = true;
  setTimeout(() => {
    button.textContent = button.dataset.label;
    button.disabled = false;
  }, ms);
}

async function copyShareLink(button) {
  const url = shareableUrl();
  // Reflect the state in the address bar regardless, so a manual copy works too.
  history.replaceState(null, "", `#s=${encodeShareState(buildShareState())}`);
  try {
    await navigator.clipboard.writeText(url);
    flashButtonLabel(button, "Link copied ✓");
  } catch {
    flashButtonLabel(button, "Link in address bar");
  }
}

function applyAdvancedValues(values) {
  for (const [key, value] of Object.entries(values)) {
    const field = advancedEngineForm.elements.namedItem(key);
    if (!field) continue;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else field.value = value;
  }
}

/** Restore a shared scenario. Returns true if it ran a simulation. */
async function applySharedState(state) {
  if (!state) return false;
  const engine = state.e || "turbojet";
  if (state.tj) {
    currentPresetInput = { ...defaultInput, ...state.tj };
    populateForm(currentPresetInput);
  }
  if (engine !== "turbojet" && advancedEngineConfigs[engine]) {
    selectEngine(engine);
    if (state.adv) applyAdvancedValues(state.adv);
    try { await runAdvancedSimulation(); } catch { /* surfaced in UI */ }
  } else {
    selectEngine("turbojet");
    try { await runSimulation(); } catch { /* surfaced in UI */ }
  }
  return true;
}

/* Public hook for the case-studies tab. Jumps to the Cycle tab, selects an
 * engine family (e.g. "turbofan"), overrides its design-point inputs with a
 * representative operating point, scrolls the console into view, and runs the
 * simulation. Mirrors the advanced branch of applySharedState. */
window.loadEngineCaseStudy = async function (family, overrides) {
  if (!advancedEngineConfigs[family]) return;
  if (typeof activateConsoleTab === "function") activateConsoleTab("dashboard");
  selectEngine(family);
  if (overrides) applyAdvancedValues(overrides);
  document
    .querySelector(".console-tabs")
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
  try { await runAdvancedSimulation(); } catch { /* surfaced in UI */ }
};

/* ------------------------------------------------------------ *
 *  8. PRESETS                                                   *
 * ------------------------------------------------------------ */

async function loadPresets() {
  const response = await fetch("/presets");
  if (!response.ok) throw new Error("Could not load presets");
  const payload = await response.json();
  presetCatalog = payload.presets || [];
  // The Cycle-tab selector is the turbojet workspace, so it only lists the
  // turbojet family. Each other architecture gets its own preset dropdown.
  presetSelect.replaceChildren();
  const turbojetFamily = presetCatalog.filter(
    (p) => p.engine_type === "turbojet" || p.engine_type === "afterburning_turbojet"
  );
  for (const preset of turbojetFamily) {
    const option = document.createElement("option");
    option.value = preset.name;
    option.textContent = preset.status ? `${preset.name} (${preset.status})` : preset.name;
    option.dataset.status = preset.status || "available";
    presetSelect.append(option);
  }
  const preferred = presetCatalog.find((p) => p.name === "PLab-01 Student Turbojet");
  const firstPreset = preferred || presetCatalog[0];
  if (firstPreset) {
    presetSelect.value = firstPreset.name;
    applyPreset(firstPreset.name);
  }
}

function applyPreset(presetName) {
  const preset = presetCatalog.find((entry) => entry.name === presetName);
  if (!preset) {
    currentPresetInput = { ...defaultInput };
    populateForm();
    return;
  }
  currentPresetInput = { ...defaultInput, ...preset.default_inputs };
  populateForm(currentPresetInput);
  $("#caseLabel").textContent =
    preset.status && preset.status !== "available" ? `${preset.name} · ${preset.status}` : preset.name;
}

/* ------------------------------------------------------------ *
 *  9. CUSTOM PROFILES (localStorage)                            *
 * ------------------------------------------------------------ */

function getCustomProfiles() {
  try { return JSON.parse(localStorage.getItem(profileStorageKey) || "[]"); }
  catch { return []; }
}
function storeCustomProfiles(profiles) {
  localStorage.setItem(profileStorageKey, JSON.stringify(profiles));
}
function refreshCustomProfiles() {
  const profiles = getCustomProfiles();
  customProfileSelect.replaceChildren();
  if (!profiles.length) {
    const option = document.createElement("option");
    option.value = ""; option.textContent = "No saved profiles";
    customProfileSelect.append(option);
    return;
  }
  for (const profile of profiles) {
    const option = document.createElement("option");
    option.value = profile.name; option.textContent = profile.name;
    customProfileSelect.append(option);
  }
}
function saveCurrentProfile() {
  const name = profileNameInput.value.trim() || "My Custom Jet";
  const profiles = getCustomProfiles().filter((p) => p.name !== name);
  profiles.push({
    name,
    engine_type: readFormInput().engine_variant,
    default_inputs: readFormInput(),
  });
  storeCustomProfiles(profiles);
  refreshCustomProfiles();
  customProfileSelect.value = name;
  $("#caseLabel").textContent = name;
}
function loadCustomProfile() {
  const profile = getCustomProfiles().find((p) => p.name === customProfileSelect.value);
  if (!profile) return false;
  profileNameInput.value = profile.name;
  currentPresetInput = { ...defaultInput, ...profile.default_inputs };
  populateForm(currentPresetInput);
  $("#caseLabel").textContent = profile.name;
  return true;
}
function deleteCustomProfile() {
  const selectedName = customProfileSelect.value;
  if (!selectedName) return;
  storeCustomProfiles(getCustomProfiles().filter((p) => p.name !== selectedName));
  refreshCustomProfiles();
}

/* ------------------------------------------------------------ *
 *  10. METRICS                                                   *
 * ------------------------------------------------------------ */

function updateMetrics(result) {
  animateMetric($("#thrustValue"), uval("thrust", result.thrust_kN, 2), result.thrust_kN);
  animateMetric($("#tsfcValue"), uval("tsfc", result.TSFC_kg_per_kN_hr, 2), result.TSFC_kg_per_kN_hr);
  $("#farValue").textContent = numberFormat(result.fuel_air_ratio, 4);
  $("#nozzleValue").textContent = result.nozzle_choked ? "Choked" : "Unchoked";
  $("#variantValue").textContent = result.engine_variant === "afterburning_turbojet" ? "Reheat" : "Dry";
  animateMetric($("#overallEtaValue"),
    `${numberFormat(result.overall_efficiency_estimate * 100, 1)} %`,
    result.overall_efficiency_estimate * 100);
}

/* ------------------------------------------------------------ *
 *  11. WARNINGS                                                  *
 * ------------------------------------------------------------ */

function parseWarning(warning) {
  const match = String(warning).match(/^(INFO|CAUTION|CRITICAL):\s*(.*)$/i);
  if (!match) return { severity: "caution", text: warning };
  return { severity: match[1].toLowerCase(), text: match[2] };
}
function renderWarnings(container, warnings) {
  if (!warnings.length) {
    container.hidden = true;
    container.replaceChildren();
    return;
  }
  container.hidden = false;
  container.replaceChildren();
  const heading = document.createElement("strong");
  heading.textContent = "Envelope checks";
  container.append(heading);
  for (const warning of warnings) {
    const parsed = parseWarning(warning);
    const item = document.createElement("div");
    item.className = `warning-item ${parsed.severity}`;
    const sev = document.createElement("span");
    sev.textContent = parsed.severity;
    const text = document.createElement("p");
    text.textContent = parsed.text;
    item.append(sev, text);
    container.append(item);
  }
}
function updateWarnings(warnings) { renderWarnings(warningsBox, warnings); }
function updateAdvancedWarnings(warnings) { renderWarnings(advancedWarningsBox, warnings); }

/* ------------------------------------------------------------ *
 *  12. STATION INSPECTOR                                         *
 * ------------------------------------------------------------ */

function stationByNumber(stationNumber) {
  if (!lastResult?.station_table || stationNumber === null || stationNumber === undefined) return null;
  return (
    lastResult.station_table[String(stationNumber)] ||
    Object.values(lastResult.station_table).find((s) => s.station === Number(stationNumber)) ||
    null
  );
}

function updateStationInspector(stationNumber = activeStation) {
  const station = stationByNumber(stationNumber);
  if (!station) {
    stationInspector.textContent = "Hover a station or section to inspect the local cycle state.";
    return;
  }
  stationInspector.replaceChildren();
  const title = document.createElement("strong");
  title.textContent = `Station ${station.station} · ${station.name}`;
  const data = document.createElement("span");
  data.className = "mono";
  data.textContent =
    `Tt ${uval("temp", station.stagnation_temperature_K, 1)}  ·  ` +
    `Pt ${uval("press", station.stagnation_pressure_Pa / 1000, 1)}  ·  ` +
    `M ${numberFormat(station.mach, 2)}  ·  ` +
    `V ${uval("vel", station.velocity_m_s, 1)}`;
  stationInspector.append(title, data);
}

function syncStationHighlights() {
  document.querySelectorAll("tr[data-station]").forEach((row) => {
    row.classList.toggle("active-station-row", Number(row.dataset.station) === Number(activeStation));
  });
}

function setActiveStation(stationNumber) {
  const next = Number(stationNumber);
  if (Number.isNaN(next)) return;
  activeStation = next;
  updateStationInspector(next);
  syncStationHighlights();
  drawEngineCrossSection();
}

/* ------------------------------------------------------------ *
 *  13. NOZZLE MODULE                                             *
 * ------------------------------------------------------------ */

function updateNozzlePanel(result) {
  if (!nozzlePanel || selectedEngine !== "turbojet") return;
  const rows = [
    ["Status", result.nozzle_expansion_status || (result.nozzle_choked ? "Choked" : "Not choked")],
    ["Choking", result.nozzle_choked ? "Choked" : "Not choked"],
    ["Exit velocity", uval("vel", result.exit_velocity_m_s, 1)],
    ["Exit pressure", uval("press", result.nozzle_exit_pressure_Pa / 1000, 1)],
    ["Ambient pressure", uval("press", result.ambient_pressure_Pa / 1000, 1)],
    ["Pressure thrust", uval("thrust", result.pressure_thrust_N / 1000, 2)],
    ["Exit area", uval("area", result.nozzle_exit_area_m2, 4)],
    ["Throat area", uval("area", result.nozzle_throat_area_m2, 4)],
    ["Area ratio", numberFormat(result.nozzle_area_ratio, 3)],
    ["Nozzle PR", numberFormat(result.nozzle_pressure_ratio, 2)],
  ];
  nozzlePanel.replaceChildren();
  const heading = document.createElement("strong");
  heading.textContent = "Nozzle · station 9";
  nozzlePanel.append(heading);
  for (const [label, value] of rows) {
    const item = document.createElement("div");
    item.className = "nozzle-item";
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("b");
    valueNode.textContent = value;
    item.append(labelNode, valueNode);
    nozzlePanel.append(item);
  }
}

/* ------------------------------------------------------------ *
 *  14. STATION TABLE                                             *
 * ------------------------------------------------------------ */

function fillStationTable(tableBody, stationTable) {
  tableBody.replaceChildren();
  for (const station of Object.values(stationTable).sort((a, b) => a.station - b.station)) {
    const row = document.createElement("tr");
    row.dataset.station = String(station.station);
    const cells = [
      station.station,
      station.name,
      unum("temp", station.stagnation_temperature_K, 1),
      unum("press", station.stagnation_pressure_Pa / 1000, 1),
      unum("temp", station.static_temperature_K, 1),
      station.static_pressure_Pa ? unum("press", station.static_pressure_Pa / 1000, 1) : ", ",
      numberFormat(station.mach, 2),
      unum("vel", station.velocity_m_s, 1),
      (station.notes || []).join("; "),
    ];
    for (const cellValue of cells) {
      const cell = document.createElement("td");
      cell.textContent = cellValue;
      row.append(cell);
    }
    row.addEventListener("mouseenter", () => setActiveStation(station.station));
    row.addEventListener("click", () => setActiveStation(station.station));
    tableBody.append(row);
  }
  syncStationHighlights();
}
function updateStationTable(stationTable) { fillStationTable(stationTableBody, stationTable); }

/* ------------------------------------------------------------ *
 *  15. CSV EXPORT                                                *
 * ------------------------------------------------------------ */

function exportStationCsv(stationTable, filename) {
  const rows = [[
    "Station", "Name", "Tt [K]", "Pt [kPa]", "Static T [K]", "Static P [kPa]",
    "Mach", "Velocity [m/s]", "Notes",
  ]];
  for (const station of Object.values(stationTable || {}).sort((a, b) => a.station - b.station)) {
    rows.push([
      station.station, station.name,
      station.stagnation_temperature_K,
      station.stagnation_pressure_Pa / 1000,
      station.static_temperature_K ?? "",
      station.static_pressure_Pa ? station.static_pressure_Pa / 1000 : "",
      station.mach ?? "",
      station.velocity_m_s ?? "",
      (station.notes || []).join("; "),
    ]);
  }
  const csv = rows
    .map((r) => r.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.style.display = "none";
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ------------------------------------------------------------ *
 *  16. CROSS-SECTION VIEWER (calm technical drawing)             *
 * ------------------------------------------------------------ */

function drawEngineCrossSection() {
  const { context: ctx, width, height } = canvasScale(engineViewerCanvas);
  ctx.clearRect(0, 0, width, height);

  const centerY = height * 0.5;
  const x = (r) => width * r;
  const yTop = (r) => centerY - height * r;
  const yBot = (r) => centerY + height * r;

  const profiles = {
    turbojet:  { start: 0.07, end: 0.94, maxRadius: 0.22, midRadius: 0.17, exitRadius: 0.075 },
    turbofan:  { start: 0.06, end: 0.95, maxRadius: 0.28, midRadius: 0.21, exitRadius: 0.085 },
    turboprop: { start: 0.08, end: 0.93, maxRadius: 0.18, midRadius: 0.14, exitRadius: 0.05 },
    ramjet:    { start: 0.07, end: 0.94, maxRadius: 0.2,  midRadius: 0.19, exitRadius: 0.12 },
    scramjet:  { start: 0.06, end: 0.96, maxRadius: 0.17, midRadius: 0.13, exitRadius: 0.15 },
  };
  const sectionMap = {
    turbojet: [
      ["Inlet",      0.08, 0.24],
      ["Compressor", 0.24, 0.48],
      ["Combustor",  0.48, 0.64],
      ["Turbine",    0.64, 0.78],
      ["Nozzle",     0.78, 0.94],
    ],
    turbofan: [
      ["Fan",          0.07, 0.22],
      ["Bypass / core",0.22, 0.43],
      ["Compressor",   0.43, 0.55],
      ["Combustor",    0.55, 0.68],
      ["Turbine",      0.68, 0.8],
      ["Nozzle",       0.8,  0.95],
    ],
    turboprop: [
      ["Inlet",        0.08, 0.22],
      ["Gearbox",      0.22, 0.36],
      ["Compressor",   0.36, 0.52],
      ["Combustor",    0.52, 0.66],
      ["Turbine",      0.66, 0.81],
      ["Exhaust",      0.81, 0.93],
    ],
    ramjet: [
      ["Diffuser",   0.07, 0.38],
      ["Combustor",  0.38, 0.7],
      ["Nozzle",     0.7,  0.94],
    ],
    scramjet: [
      ["Compression inlet", 0.06, 0.34],
      ["Isolator",          0.34, 0.48],
      ["Combustor",         0.48, 0.75],
      ["Expansion nozzle",  0.75, 0.96],
    ],
  };
  const sectionStations = {
    turbojet: { Inlet: 2, Compressor: 3, Combustor: 4, Turbine: 5, Nozzle: 9 },
    turbofan: { Fan: 13, "Bypass / core": 13, Compressor: 3, Combustor: 4, Turbine: 5, Nozzle: 9 },
    turboprop: { Inlet: 2, Gearbox: 5, Compressor: 3, Combustor: 4, Turbine: 5, Exhaust: 9 },
    ramjet: { Diffuser: 2, Combustor: 4, Nozzle: 9 },
    scramjet: { "Compression inlet": 2, Isolator: 3, Combustor: 4, "Expansion nozzle": 9 },
  };
  const stationMarkerMap = {
    turbojet:  [[0,0.05],[2,0.24],[3,0.48],[4,0.64],[5,0.78],[9,0.94]],
    turbofan:  [[0,0.05],[2,0.2],[13,0.36],[3,0.55],[4,0.68],[5,0.8],[9,0.95]],
    turboprop: [[0,0.05],[2,0.22],[3,0.52],[4,0.66],[5,0.81],[9,0.93]],
    ramjet:    [[0,0.05],[2,0.38],[4,0.7],[9,0.94]],
    scramjet:  [[0,0.05],[2,0.34],[3,0.48],[4,0.75],[9,0.96]],
  };
  const architectureInfo = {
    turbojet: {
      path:  "0 ambient → 2 inlet → 3 compressor → 4 combustor → 5 turbine → 9 nozzle",
      use:   "Use the station path to connect cycle jumps to thrust, TSFC, and nozzle choking.",
      check: "Watch compressor PR, turbine inlet temperature, and nozzle state.",
    },
    turbofan: {
      path:  "0 → 2 inlet → 13 fan / bypass · core 3 → 4 → 5 → 9 / 19 nozzles",
      use:   "Use it to separate core thrust from bypass-flow effects.",
      check: "Watch bypass ratio, fan PR, and core nozzle choking.",
    },
    turboprop: {
      path:  "0 → 2 inlet → 3 compressor → 4 combustor → 5 power turbine → exhaust",
      use:   "Shaft power dominates over residual jet thrust.",
      check: "Watch propeller work fraction, shaft power, residual nozzle velocity.",
    },
    ramjet: {
      path:  "0 freestream → 2 diffuser → 4 combustor → 9 nozzle",
      use:   "Ram compression without rotating machinery.",
      check: "Watch Mach, inlet recovery, and combustor pressure loss.",
    },
    scramjet: {
      path:  "0 hypersonic → 2 inlet → 3 isolator → 4 combustor → 9 nozzle",
      use:   "Supersonic-combustion architecture.",
      check: "Watch Mach, combustor Mach, inlet recovery, and expansion nozzle.",
    },
  };

  const profile = profiles[selectedEngine] || profiles.turbojet;
  const sections = sectionMap[selectedEngine] || sectionMap.turbojet;
  const info = architectureInfo[selectedEngine] || architectureInfo.turbojet;
  const stationFor = sectionStations[selectedEngine] || sectionStations.turbojet;
  const stationMarkers = stationMarkerMap[selectedEngine] || stationMarkerMap.turbojet;
  engineViewerHitRegions = [];

  /* ===== nacelle silhouette ===== */
  function silhouettePath() {
    const path = new Path2D();
    path.moveTo(x(profile.start), centerY);
    path.bezierCurveTo(
      x(profile.start + 0.08), yTop(profile.maxRadius * 0.85),
      x(profile.start + 0.24), yTop(profile.maxRadius),
      x(0.5), yTop(profile.midRadius));
    path.bezierCurveTo(
      x(0.7), yTop(profile.midRadius * 0.95),
      x(profile.end - 0.08), yTop(profile.exitRadius),
      x(profile.end), centerY);
    path.bezierCurveTo(
      x(profile.end - 0.08), yBot(profile.exitRadius),
      x(0.7), yBot(profile.midRadius * 0.95),
      x(0.5), yBot(profile.midRadius));
    path.bezierCurveTo(
      x(profile.start + 0.24), yBot(profile.maxRadius),
      x(profile.start + 0.08), yBot(profile.maxRadius * 0.85),
      x(profile.start), centerY);
    path.closePath();
    return path;
  }
  const shell = silhouettePath();

  /* ===== subtle section bands ===== */
  ctx.save();
  ctx.clip(shell);
  for (const [label, startR, endR] of sections) {
    const stationNumber = stationFor[label];
    const isActive = Number(stationNumber) === Number(activeStation);
    const region = {
      label, station: stationNumber,
      x0: x(startR), x1: x(endR),
      y0: yTop(profile.maxRadius), y1: yBot(profile.maxRadius),
    };
    engineViewerHitRegions.push(region);

    ctx.fillStyle = isActive
      ? "rgba(255, 255, 255, 0.06)"
      : "rgba(255, 255, 255, 0.012)";
    ctx.fillRect(
      x(startR), yTop(profile.maxRadius),
      x(endR - startR), height * profile.maxRadius * 2);

    // thin vertical divider on the right edge
    ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x(endR), yTop(profile.maxRadius));
    ctx.lineTo(x(endR), yBot(profile.maxRadius));
    ctx.stroke();
  }
  ctx.restore();

  /* ===== nacelle outline ===== */
  ctx.strokeStyle = "rgba(244, 244, 245, 0.62)";
  ctx.lineWidth = 1;
  ctx.stroke(shell);

  /* ===== centerline ===== */
  ctx.beginPath();
  ctx.moveTo(x(profile.start + 0.02), centerY);
  ctx.lineTo(x(profile.end - 0.02), centerY);
  ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
  ctx.setLineDash([2.4, 3]);
  ctx.lineWidth = 0.75;
  ctx.stroke();
  ctx.setLineDash([]);

  /* ===== section labels ===== */
  ctx.font = "500 10.5px 'Inter', system-ui";
  ctx.textAlign = "center";
  for (const [label, startR, endR] of sections) {
    const stationNumber = stationFor[label];
    const isActive = Number(stationNumber) === Number(activeStation);
    const labelX = x((startR + endR) / 2);
    const labelWidth = x(endR - startR);
    if (labelWidth < 70) continue;
    ctx.fillStyle = isActive ? "rgba(244, 244, 245, 0.95)" : "rgba(244, 244, 245, 0.55)";
    ctx.fillText(label.toUpperCase(), labelX, centerY + 4);
  }
  ctx.textAlign = "left";

  /* ===== station axis below ===== */
  const axisY = yBot(profile.maxRadius * 1.32);
  ctx.beginPath();
  ctx.moveTo(x(profile.start - 0.02), axisY);
  ctx.lineTo(x(profile.end + 0.02), axisY);
  ctx.strokeStyle = "rgba(255, 255, 255, 0.10)";
  ctx.lineWidth = 0.75;
  ctx.stroke();

  /* ===== station markers ===== */
  ctx.font = "500 10px 'JetBrains Mono', ui-monospace, monospace";
  ctx.textAlign = "center";
  for (const [stationNumber, ratio] of stationMarkers) {
    const markerX = x(ratio);
    const isActive = Number(stationNumber) === Number(activeStation);
    // leader from engine to axis
    ctx.beginPath();
    ctx.moveTo(markerX, yBot(profile.maxRadius));
    ctx.lineTo(markerX, axisY);
    ctx.strokeStyle = isActive ? "rgba(244, 244, 245, 0.9)" : "rgba(255, 255, 255, 0.16)";
    ctx.lineWidth = isActive ? 1 : 0.75;
    ctx.stroke();

    // marker
    ctx.beginPath();
    ctx.arc(markerX, axisY, isActive ? 4 : 3, 0, Math.PI * 2);
    ctx.fillStyle = isActive ? "#f4f4f5" : palette.surface;
    ctx.fill();
    ctx.strokeStyle = isActive ? "#f4f4f5" : "rgba(255, 255, 255, 0.32)";
    ctx.lineWidth = 1;
    ctx.stroke();

    // station number
    ctx.fillStyle = isActive ? "rgba(244, 244, 245, 0.95)" : "rgba(244, 244, 245, 0.48)";
    ctx.fillText(String(stationNumber), markerX, axisY + 18);
  }
  ctx.textAlign = "left";

  /* ===== legend insights ===== */
  const legend = document.querySelector("#engineViewerLegend");
  legend.replaceChildren();
  const insights = [
    ["Station path", info.path],
    ["How to read this", info.use],
    ["What to check", info.check],
  ];
  for (const [label, value] of insights) {
    const item = document.createElement("article");
    item.className = "viewer-insight";
    const title = document.createElement("span");
    title.textContent = label;
    const body = document.createElement("strong");
    body.textContent = value;
    item.append(title, body);
    legend.append(item);
  }
}

/* ------------------------------------------------------------ *
 *  17. CHART FRAME (hairline only)                               *
 * ------------------------------------------------------------ */

function drawChartFrame(ctx, x, y, w, h) {
  // horizontal gridlines only (less noise than full grid)
  ctx.strokeStyle = palette.grid;
  ctx.lineWidth = 1;
  ctx.beginPath();
  const rows = 4;
  for (let j = 1; j < rows; j += 1) {
    const gy = y + (h * j) / rows;
    ctx.moveTo(x, gy);
    ctx.lineTo(x + w, gy);
  }
  ctx.stroke();
  // baseline + axis
  ctx.strokeStyle = palette.gridStrong;
  ctx.beginPath();
  ctx.moveTo(x, y + h + 0.5);
  ctx.lineTo(x + w, y + h + 0.5);
  ctx.moveTo(x + 0.5, y);
  ctx.lineTo(x + 0.5, y + h);
  ctx.stroke();
}

/* ------------------------------------------------------------ *
 *  18. CHART HELPERS                                             *
 * ------------------------------------------------------------ */

function drawSeriesLine(ctx, points, color, lineWidth = 1.5) {
  ctx.beginPath();
  points.forEach(([px, py], i) => i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py));
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.stroke();
}

function drawSeriesAreaFill(ctx, points, baseY, color) {
  if (points.length < 2) return;
  ctx.beginPath();
  points.forEach(([px, py], i) => i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py));
  ctx.lineTo(points[points.length - 1][0], baseY);
  ctx.lineTo(points[0][0], baseY);
  ctx.closePath();
  // very subtle 3% fill
  ctx.fillStyle = color + "10";  // ~6% alpha
  ctx.fill();
}

function drawSeriesDots(ctx, points, color) {
  for (const [px, py] of points) {
    ctx.beginPath();
    ctx.arc(px, py, 2.4, 0, Math.PI * 2);
    ctx.fillStyle = palette.surface;
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}

function drawSeriesLabel(ctx, text, x, y, color) {
  ctx.fillStyle = color;
  ctx.font = "500 11px 'Inter', system-ui";
  ctx.fillText(text, x, y);
}

/* ------------------------------------------------------------ *
 *  19. STATION CHART                                             *
 * ------------------------------------------------------------ */

/** True when the user has asked the OS to minimise motion. */
const prefersReducedMotion = window.matchMedia
  ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
  : false;

/**
 * One-shot animated wrapper around drawStationChart. Sweeps the traces in
 * left-to-right over ~520 ms, then settles on the final frame. Self-
 * terminating, no persistent rAF loop. Honours reduced-motion by drawing the
 * final frame immediately.
 */
function animateStationChart(result, targetCanvas = stationCanvas) {
  if (prefersReducedMotion) {
    drawStationChart(result, targetCanvas, 1);
    return;
  }
  const t0 = performance.now();
  const duration = 520;
  const step = (now) => {
    const t = Math.min(1, (now - t0) / duration);
    drawStationChart(result, targetCanvas, easeOutCubic(t));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* Order stations by physical flow position, not raw number, so charts read
 * inlet → exhaust. Standard SAE numbering puts the inter-turbine station 45
 * between the burner (4) and the LP-turbine exit (5), and the bypass stations
 * (13, 19) form a cold tail after the core, sorting numerically would scatter
 * them and make the traces look broken. */
const STATION_FLOW_RANK = {
  0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 41: 4.3, 44: 4.6, 45: 5, 49: 5.5, 5: 6, 55: 6.5,
  6: 7, 7: 7.5, 8: 7.8, 9: 8, 13: 9, 16: 9.3, 18: 9.6, 19: 10, 21: 11, 25: 12,
};
function stationFlowKey(n) {
  return STATION_FLOW_RANK[n] !== undefined ? STATION_FLOW_RANK[n] : 100 + Number(n);
}
function byFlowOrder(a, b) { return stationFlowKey(a.station) - stationFlowKey(b.station); }

/* Interpolate the real thermodynamic process between consecutive stations so the
 * cycle diagram is drawn with curves, not straight chords (which cross and look
 * unphysical). For P-v use the polytropic relation P·vⁿ = const; for T-s use the
 * exponential T = T₁·exp(k(s−s₁)) that an ideal gas follows along a process.
 * Interpolated points carry station = null so only the real stations get dots
 * and labels. */
function interpolateProcess(points, mode) {
  if (points.length < 2) return points;
  const out = [];
  const N = 16;
  for (let k = 0; k < points.length - 1; k++) {
    const a = points[k], b = points[k + 1];
    out.push({ station: a.station, x: a.x, y: a.y });
    for (let j = 1; j < N; j++) {
      const t = j / N;
      const x = a.x + (b.x - a.x) * t;
      let y;
      if (mode === "power" && a.x > 0 && b.x > 0 && a.y > 0 && b.y > 0 &&
          Math.abs(Math.log(b.x / a.x)) > 1e-6 && x > 0) {
        const n = Math.log(a.y / b.y) / Math.log(b.x / a.x);   // P·vⁿ = const
        y = a.y * Math.pow(a.x / x, n);
      } else if (mode === "exp" && Math.abs(b.x - a.x) > 1e-9 && a.y > 0 && b.y > 0) {
        const kk = Math.log(b.y / a.y) / (b.x - a.x);          // T = T₁·exp(k·Δs)
        y = a.y * Math.exp((x - a.x) * kk);
      } else {
        y = a.y + (b.y - a.y) * t;                              // linear fallback
      }
      out.push({ station: null, x, y });
    }
  }
  const last = points[points.length - 1];
  out.push({ station: last.station, x: last.x, y: last.y });
  return out;
}

function drawStationChart(result, targetCanvas = stationCanvas, progress = 1) {
  const { context: ctx, width, height } = canvasScale(targetCanvas);
  const stations = Object.values(result.station_table).sort(byFlowOrder);
  ctx.clearRect(0, 0, width, height);

  const pad = 40;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  drawChartFrame(ctx, pad, pad, plotW, plotH);

  const maxTemp = Math.max(...stations.map((s) => s.stagnation_temperature_K));
  const maxPress = Math.max(...stations.map((s) => s.stagnation_pressure_Pa / 1000));

  function point(i, value, max) {
    return [
      pad + (plotW * i) / Math.max(1, stations.length - 1),
      pad + plotH - (plotH * value) / max,
    ];
  }

  const tempPoints = stations.map((s, i) => point(i, s.stagnation_temperature_K, maxTemp));
  const pressPoints = stations.map((s, i) => point(i, s.stagnation_pressure_Pa / 1000, maxPress));

  // Progressive left-to-right reveal: clip the series to a rectangle whose
  // width grows with `progress`. The frame, axis numbers, and labels are drawn
  // unclipped so they stay stable while the traces draw in like an
  // oscilloscope sweep.
  ctx.save();
  if (progress < 1) {
    ctx.beginPath();
    ctx.rect(pad, pad - 6, plotW * progress, plotH + 12);
    ctx.clip();
  }
  drawSeriesAreaFill(ctx, tempPoints, pad + plotH, palette.temperature);
  drawSeriesAreaFill(ctx, pressPoints, pad + plotH, palette.pressure);
  drawSeriesLine(ctx, tempPoints, palette.temperature);
  drawSeriesLine(ctx, pressPoints, palette.pressure);
  drawSeriesDots(ctx, tempPoints, palette.temperature);
  drawSeriesDots(ctx, pressPoints, palette.pressure);
  ctx.restore();

  drawSeriesLabel(ctx, "Tt  [K]", pad + 4, pad - 14, palette.temperature);
  drawSeriesLabel(ctx, "Pt  [kPa]", pad + 80, pad - 14, palette.pressure);

  // x-axis: station numbers
  ctx.fillStyle = palette.textDim;
  ctx.font = "500 10.5px 'JetBrains Mono', ui-monospace, monospace";
  ctx.textAlign = "center";
  stations.forEach((s, i) => {
    const xx = pad + (plotW * i) / Math.max(1, stations.length - 1);
    ctx.fillText(String(s.station), xx, height - 16);
  });
  ctx.textAlign = "left";

  // range hints
  ctx.fillStyle = palette.textDim;
  ctx.font = "500 10px 'JetBrains Mono', ui-monospace, monospace";
  ctx.fillText(`max Tt ${numberFormat(maxTemp, 0)} K`, pad + 4, height - 2);
  ctx.textAlign = "right";
  ctx.fillText(`max Pt ${numberFormat(maxPress, 0)} kPa`, width - pad - 4, height - 2);
  ctx.textAlign = "left";
}

/* ------------------------------------------------------------ *
 *  20. SWEEP CHART                                               *
 * ------------------------------------------------------------ */

function drawSweepChart(payload) {
  const { context: ctx, width, height } = canvasScale(sweepCanvas);
  ctx.clearRect(0, 0, width, height);
  const successes = payload.cases.filter((e) => e.success && e.output);

  const pad = 48;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  drawChartFrame(ctx, pad, pad, plotW, plotH);

  if (!successes.length) {
    ctx.fillStyle = palette.textDim;
    ctx.font = "500 12px 'Inter', system-ui";
    ctx.fillText("No successful sweep cases", pad + 8, pad + 22);
    return;
  }

  const maxThrust = Math.max(...successes.map((e) => e.output.thrust_kN));
  const maxTsfc = Math.max(...successes.map((e) => e.output.TSFC_kg_per_kN_hr));

  function pts(getter, max) {
    return successes.map((entry, i) => [
      pad + (plotW * i) / Math.max(1, successes.length - 1),
      pad + plotH - (plotH * getter(entry.output)) / max,
    ]);
  }

  const thrustPts = pts((o) => o.thrust_kN, maxThrust);
  const tsfcPts = pts((o) => o.TSFC_kg_per_kN_hr, maxTsfc);

  drawSeriesAreaFill(ctx, thrustPts, pad + plotH, palette.thrust);
  drawSeriesLine(ctx, thrustPts, palette.thrust);
  drawSeriesLine(ctx, tsfcPts, palette.tsfc);
  drawSeriesDots(ctx, thrustPts, palette.thrust);
  drawSeriesDots(ctx, tsfcPts, palette.tsfc);

  drawSeriesLabel(ctx, "Thrust  [kN]", pad + 4, pad - 14, palette.thrust);
  drawSeriesLabel(ctx, "TSFC  [kg/kN/hr]", pad + 110, pad - 14, palette.tsfc);

  ctx.fillStyle = palette.textDim;
  ctx.font = "500 10.5px 'JetBrains Mono', ui-monospace, monospace";
  ctx.textAlign = "center";
  successes.forEach((entry, i) => {
    const xx = pad + (plotW * i) / Math.max(1, successes.length - 1);
    ctx.fillText(numberFormat(entry.input_value, 1), xx, height - 16);
  });
  ctx.textAlign = "left";
}

/* ------------------------------------------------------------ *
 *  21. PLACEHOLDER / LINE / BAR / XY                             *
 * ------------------------------------------------------------ */

function drawPlaceholder(canvas, message) {
  const { context: ctx, width, height } = canvasScale(canvas);
  ctx.clearRect(0, 0, width, height);
  const pad = 40;
  drawChartFrame(ctx, pad, pad, width - pad * 2, height - pad * 2);
  ctx.fillStyle = palette.textDim;
  ctx.font = "500 12px 'Inter', system-ui";
  ctx.fillText(message, pad + 8, pad + 22);
}

function drawLineGraph(canvas, labels, values, color, unitLabel, xLabel = "Station") {
  const { context: ctx, width, height } = canvasScale(canvas);
  ctx.clearRect(0, 0, width, height);
  if (!values.length) { drawPlaceholder(canvas, "No graph data yet"); return; }

  const pad = 44;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  drawChartFrame(ctx, pad, pad, plotW, plotH);

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const span = Math.max(1e-9, maxValue - minValue);

  ctx.fillStyle = palette.textDim;
  ctx.font = "500 10px 'JetBrains Mono', ui-monospace, monospace";
  ctx.fillText(numberFormat(maxValue, 1), 8, pad + 4);
  ctx.fillText(numberFormat(minValue, 1), 8, pad + plotH);

  const pts = values.map((v, i) => [
    pad + (plotW * i) / Math.max(1, values.length - 1),
    pad + plotH - (plotH * (v - minValue)) / span,
  ]);

  drawSeriesAreaFill(ctx, pts, pad + plotH, color);
  drawSeriesLine(ctx, pts, color);
  drawSeriesDots(ctx, pts, color);

  drawSeriesLabel(ctx, unitLabel, pad + 4, pad - 14, color);

  ctx.fillStyle = palette.textDim;
  ctx.font = "500 10.5px 'JetBrains Mono', ui-monospace, monospace";
  ctx.textAlign = "center";
  labels.forEach((label, i) => {
    const xx = pad + (plotW * i) / Math.max(1, labels.length - 1);
    ctx.fillText(String(label), xx, height - 16);
  });
  ctx.font = "500 10px 'Inter', system-ui";
  ctx.fillText(xLabel, pad + plotW / 2, height - 2);
  ctx.textAlign = "left";
}

function drawBarGraph(canvas, labels, values, colors, unitLabel, fixedMaxValue = null) {
  const { context: ctx, width, height } = canvasScale(canvas);
  ctx.clearRect(0, 0, width, height);
  const pad = 44;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  drawChartFrame(ctx, pad, pad, plotW, plotH);

  // Headroom (×1.18) so the tallest bar never reaches the top, its value label
  // is drawn above the bar on the dark background, not buried inside it.
  const maxValue = fixedMaxValue || Math.max(1e-9, ...values.map((v) => Math.abs(v))) * 1.18;
  const slot = plotW / Math.max(1, values.length);
  const barWidth = Math.max(28, slot - 32);

  if (fixedMaxValue) {
    ctx.fillStyle = palette.textDim;
    ctx.font = "500 10px 'JetBrains Mono', ui-monospace, monospace";
    ctx.fillText(String(fixedMaxValue), 8, pad + 4);
    ctx.fillText("0", 18, pad + plotH);
  }

  values.forEach((value, i) => {
    const x = pad + i * slot + (slot - barWidth) / 2;
    const barHeight = (Math.min(Math.abs(value), maxValue) / maxValue) * plotH;
    const y = pad + plotH - barHeight;
    const color = colors[i % colors.length];

    ctx.fillStyle = color;
    ctx.fillRect(x, y, barWidth, barHeight);

    ctx.fillStyle = palette.textDim;
    ctx.font = "500 11px 'Inter', system-ui";
    ctx.textAlign = "center";
    ctx.fillText(labels[i], x + barWidth / 2, height - 16);

    ctx.fillStyle = palette.ink;
    ctx.font = "500 11px 'JetBrains Mono', ui-monospace, monospace";
    ctx.fillText(numberFormat(value, 1), x + barWidth / 2, Math.max(pad + 12, y - 8));
  });
  ctx.textAlign = "left";

  drawSeriesLabel(ctx, unitLabel, pad + 4, pad - 14, palette.text);
}

/* Stagnation-property cycle-diagram coordinates for one station.
 *
 * Both the T-s and P-v diagrams are drawn on a CONSISTENT stagnation basis: the
 * mid-cycle stations (compressor, combustor, turbine, fan) carry only stagnation
 * properties in this reduced-order model, so using stagnation Tt/Pt everywhere
 * avoids silently mixing static and stagnation points on the same axes.
 *
 *   entropy        s  = cp·ln(Tt/Tref) − R·ln(Pt/Pref)   [relative datum]
 *   specific vol.  v  = R·Tt / Pt                          (ideal gas)
 *
 * Entropy is on a relative reference datum and the specific-heat changes from
 * cp_air to cp_gas across the combustor, so the s-axis is qualitative (the
 * cycle SHAPE is meaningful; the absolute entropy zero is not). */
function stationThermoProperties(station) {
  const totalT = station.stagnation_temperature_K;
  const totalP = station.stagnation_pressure_Pa;
  const isCombustionGas =
    station.station >= 4 && station.station !== 13 && station.station !== 19;
  const gasCp = isCombustionGas ? thermoReference.cpGas : thermoReference.cpAir;
  const entropy = (gasCp * Math.log(totalT / thermoReference.temperatureK)
    - thermoReference.rAir * Math.log(totalP / thermoReference.pressurePa)) / 1000;
  const specificVolume = (thermoReference.rAir * totalT) / totalP;
  return {
    station: station.station,
    entropyKjKgK: entropy,
    pressureKPa: totalP / 1000,
    specificVolume,
    temperatureK: totalT,
  };
}

/** "Nice number" ticks (Heckbert 1990 style), returns ~5 round values. */
function niceTicks(min, max, targetCount = 5) {
  const range = Math.max(1e-12, max - min);
  const roughStep = range / targetCount;
  const magnitude = Math.pow(10, Math.floor(Math.log10(roughStep)));
  const norm = roughStep / magnitude;
  const niceStep =
    (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * magnitude;
  const start = Math.ceil(min / niceStep) * niceStep;
  const out = [];
  for (let v = start; v <= max + niceStep * 1e-6; v += niceStep) {
    out.push(Number(v.toFixed(12)));
  }
  return out;
}

function formatTick(value) {
  const abs = Math.abs(value);
  if (abs === 0) return "0";
  if (abs >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (abs >= 10) return value.toFixed(1);
  if (abs >= 1) return value.toFixed(2);
  return value.toPrecision(2);
}

function drawXYGraph(canvas, points, options) {
  const { context: ctx, width, height } = canvasScale(canvas);
  ctx.clearRect(0, 0, width, height);
  if (points.length < 2) { drawPlaceholder(canvas, "No thermodynamic data yet"); return; }

  const padLeft = 64, padRight = 22, padTop = 36, padBottom = 44;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;
  drawChartFrame(ctx, padLeft, padTop, plotW, plotH);

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  // Pad the y-range a touch so the top point isn't clipped by the frame.
  const padFracY = 0.08;
  const yLo = minY - padFracY * Math.max(1e-9, maxY - minY);
  const yHi = maxY + padFracY * Math.max(1e-9, maxY - minY);
  const spanX = Math.max(1e-9, maxX - minX);
  const spanY = Math.max(1e-9, yHi - yLo);

  const xToPx = (x) => padLeft + ((x - minX) / spanX) * plotW;
  const yToPx = (y) => padTop + plotH - ((y - yLo) / spanY) * plotH;

  const pts = points.map((p) => [xToPx(p.x), yToPx(p.y)]);

  // numeric tick marks on both axes
  ctx.fillStyle = palette.textDim;
  ctx.font = "500 10px 'JetBrains Mono', ui-monospace, monospace";
  ctx.textAlign = "right";
  for (const yv of niceTicks(yLo, yHi, 5)) {
    const py = yToPx(yv);
    if (py < padTop - 1 || py > padTop + plotH + 1) continue;
    ctx.fillText(formatTick(yv), padLeft - 6, py + 3);
  }
  ctx.textAlign = "center";
  for (const xv of niceTicks(minX, maxX, 5)) {
    const px = xToPx(xv);
    if (px < padLeft - 1 || px > padLeft + plotW + 1) continue;
    ctx.fillText(formatTick(xv), px, padTop + plotH + 14);
  }
  ctx.textAlign = "left";

  drawSeriesAreaFill(ctx, pts, padTop + plotH, options.color);
  drawSeriesLine(ctx, pts, options.color);
  // Dots only on the real stations, interpolated process points have station == null.
  drawSeriesDots(ctx, pts.filter((_, i) => points[i].station != null), options.color);

  // station labels with simple greedy collision avoidance, when two label
  // positions are within COLLISION_PX, offset the second by a vertical step.
  ctx.fillStyle = palette.text;
  ctx.font = "600 10.5px 'JetBrains Mono', ui-monospace, monospace";
  const COLLISION_PX = 22;
  const placedLabels = [];  // {x, y} of label anchor points already placed
  pts.forEach(([px, py], i) => {
    if (points[i].station == null) return;     // skip interpolated process points
    let lx = px + 6;
    let ly = py - 6;
    let attempt = 0;
    while (
      attempt < 6 &&
      placedLabels.some(
        (p) => Math.hypot(p.x - lx, p.y - ly) < COLLISION_PX,
      )
    ) {
      attempt += 1;
      ly = py - 6 + attempt * 12 * (attempt % 2 === 1 ? 1 : -1);
    }
    placedLabels.push({ x: lx, y: ly });
    ctx.fillText(String(points[i].station), lx, ly);
  });

  if (options.title) {
    drawSeriesLabel(ctx, options.title, padLeft + 4, padTop - 14, options.color);
  }
  ctx.fillStyle = palette.textDim;
  ctx.font = "500 11px 'Inter', system-ui";
  ctx.textAlign = "center";
  ctx.fillText(options.xLabel, padLeft + plotW / 2, height - 10);
  ctx.save();
  ctx.translate(16, padTop + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(options.yLabel, 0, 0);
  ctx.restore();
  ctx.textAlign = "left";
}

function updateGraphCanvases() {
  if (!lastResult) {
    // Engine switched without a fresh run, wipe the charts so stale stations
    // from a previous architecture don't bleed across.
    [
      "#graphStationTemp", "#graphStationPressure", "#graphTsDiagram",
      "#graphPvDiagram", "#graphEfficiency", "#graphThrustBreakdown",
      "#graphSweepThrust", "#graphSweepTsfc",
    ].forEach((sel) => {
      const c = $(sel);
      if (c) drawPlaceholder(c, "Run a cycle to populate this chart");
    });
    return;
  }
  const stations = Object.values(lastResult.station_table).sort(byFlowOrder);
  const stationLabels = stations.map((s) => s.station);

  drawLineGraph($("#graphStationTemp"), stationLabels,
    stations.map((s) => s.stagnation_temperature_K),
    palette.temperature, "Tt [K] · stagnation");
  drawLineGraph($("#graphStationPressure"), stationLabels,
    stations.map((s) => s.stagnation_pressure_Pa / 1000),
    palette.pressure, "Pt [kPa] · stagnation");

  // The T-s / P-v cycle loop is the *core* Brayton cycle. The bypass-duct
  // stations (13/16/18/19) are a separate cold stream, including them in the
  // connecting line makes it jump out to the bypass and dangle, breaking the
  // loop. They still appear on the station temperature/pressure charts above.
  const CYCLE_BYPASS = new Set([13, 16, 18, 19]);
  const thermo = stations
    .filter((s) => !CYCLE_BYPASS.has(Number(s.station)))
    .map(stationThermoProperties);
  drawXYGraph($("#graphTsDiagram"),
    interpolateProcess(
      thermo.map((p) => ({ station: p.station, x: p.entropyKjKgK, y: p.temperatureK })), "exp"),
    { color: palette.temperature, title: "", xLabel: "s  [kJ/kg·K]", yLabel: "Tt [K] · stagnation" });
  drawXYGraph($("#graphPvDiagram"),
    interpolateProcess(
      thermo.map((p) => ({ station: p.station, x: p.specificVolume, y: p.pressureKPa })), "power"),
    { color: palette.pressure, title: "", xLabel: "v  [m³/kg] · stagnation", yLabel: "Pt [kPa] · stagnation" });

  drawBarGraph($("#graphEfficiency"),
    ["thermal", "prop", "overall"],
    [
      lastResult.thermal_efficiency_estimate * 100,
      lastResult.propulsive_efficiency_estimate * 100,
      lastResult.overall_efficiency_estimate * 100,
    ],
    [palette.efficiency, palette.prop, palette.overall],
    "Efficiency  [%]", 100);

  drawBarGraph($("#graphThrustBreakdown"),
    ["momentum", "pressure"],
    [lastResult.momentum_thrust_N / 1000, lastResult.pressure_thrust_N / 1000],
    [palette.thrust, palette.tsfc],
    "Thrust  [kN]");

  if (selectedEngine !== "turbojet") {
    drawPlaceholder($("#graphSweepThrust"), "Turbojet sweep only for now");
    drawPlaceholder($("#graphSweepTsfc"), "Turbojet sweep only for now");
    return;
  }
  if (!lastSweepPayload) {
    drawPlaceholder($("#graphSweepThrust"), "Run a sweep first");
    drawPlaceholder($("#graphSweepTsfc"), "Run a sweep first");
    return;
  }
  const successes = lastSweepPayload.cases.filter((e) => e.success && e.output);
  const sweepLabels = successes.map((e) => e.input_value);
  const sweepXLabel = $("#sweepParameter").selectedOptions[0]?.textContent || "Sweep input";
  drawLineGraph($("#graphSweepThrust"), sweepLabels,
    successes.map((e) => e.output.thrust_kN),
    palette.thrust, "Thrust  [kN]", sweepXLabel);
  drawLineGraph($("#graphSweepTsfc"), sweepLabels,
    successes.map((e) => e.output.TSFC_kg_per_kN_hr),
    palette.tsfc, "TSFC  [kg/kN/hr]", sweepXLabel);
}

/* ------------------------------------------------------------ *
 *  22. SWEEP SUMMARY                                             *
 * ------------------------------------------------------------ */

function describeDirection(start, end, metric, lowerIsBetter = false) {
  const delta = end - start;
  if (Math.abs(delta) < Math.max(1e-9, Math.abs(start) * 0.002)) {
    return `${metric} stayed about the same.`;
  }
  const direction = delta > 0 ? "increased" : "decreased";
  const better = lowerIsBetter
    ? (delta < 0 ? "improved" : "worsened")
    : (delta > 0 ? "improved" : "reduced");
  return `${metric} ${direction} from ${numberFormat(start, 2)} to ${numberFormat(end, 2)}, so it ${better} over this sweep.`;
}

function updateSweepExplanation(payload) {
  const explanation = $("#sweepExplanation");
  const successes = payload.cases.filter((e) => e.success && e.output);
  if (successes.length < 2) {
    explanation.textContent = "Run at least two successful sweep cases to compare the trend.";
    return;
  }
  const first = successes[0].output;
  const last = successes[successes.length - 1].output;
  const chokedCount = successes.filter((e) => e.output.nozzle_choked).length;
  const unchokedCount = successes.length - chokedCount;
  const chokingText = chokedCount === successes.length
    ? "Nozzle stayed choked for every successful case."
    : unchokedCount === successes.length
      ? "Nozzle stayed unchoked for every successful case."
      : `Nozzle choking changed across the sweep: ${chokedCount} choked, ${unchokedCount} unchoked.`;
  explanation.textContent = [
    describeDirection(first.thrust_kN, last.thrust_kN, "Thrust"),
    describeDirection(first.TSFC_kg_per_kN_hr, last.TSFC_kg_per_kN_hr, "TSFC", true),
    chokingText,
  ].join(" ");
}

/* ------------------------------------------------------------ *
 *  23. ADVANCED FORMS                                            *
 * ------------------------------------------------------------ */

function renderAdvancedInputs() {
  const config = advancedEngineConfigs[selectedEngine];
  if (!config) return;
  $("#advancedFormTitle").textContent = config.title;
  $("#advancedRouteLabel").textContent = config.route;
  $("#runAdvancedButton").textContent = `Run ${engineLabels[selectedEngine].toLowerCase()}`;
  advancedInputGrid.replaceChildren();

  for (const field of config.fields) {
    const [key, label, unit, opts] = field;
    const wrapper = document.createElement("label");
    const labelLine = document.createElement("span");
    labelLine.textContent = label;
    if (unit) {
      const u = document.createElement("span");
      u.className = "unit";
      u.textContent = unit;
      labelLine.append(" ", u);
    }
    let input;
    if (opts?.type === "select") {
      input = document.createElement("select");
      input.name = key;
      for (const [value, optLabel] of opts.options) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = optLabel;
        if (config.defaults[key] === value) option.selected = true;
        input.append(option);
      }
    } else if (opts?.type === "checkbox") {
      input = document.createElement("input");
      input.name = key;
      input.type = "checkbox";
      input.checked = Boolean(config.defaults[key]);
      wrapper.classList.add("checkbox-line");
    } else {
      input = document.createElement("input");
      input.name = key;
      input.type = "number";
      input.step = "any";
      input.value = config.defaults[key];
    }
    wrapper.append(labelLine, input);
    advancedInputGrid.append(wrapper);
  }
  populateAdvancedPresets();
  renderAdvancedSweepControls(config);
}

/* Fill the advanced-engine preset dropdown with only this architecture's presets. */
function populateAdvancedPresets() {
  const sel = $("#advancedPresetSelect");
  if (!sel) return;
  sel.replaceChildren();
  const base = document.createElement("option");
  base.value = ""; base.textContent = "Default (no preset)";
  sel.append(base);
  for (const p of presetCatalog.filter((p) => p.engine_type === selectedEngine)) {
    const o = document.createElement("option");
    o.value = p.name;
    o.textContent = p.status && p.status !== "available" ? `${p.name} (${p.status})` : p.name;
    sel.append(o);
  }
}

/* Apply a preset's inputs to the currently-rendered advanced form. */
function applyAdvancedPreset(name) {
  const config = advancedEngineConfigs[selectedEngine];
  if (!config) return;
  const preset = presetCatalog.find((p) => p.name === name);
  if (!preset) { renderAdvancedInputs(); $("#advancedCaseLabel").textContent = "Awaiting run"; return; }
  const di = preset.default_inputs || {};
  for (const field of config.fields) {
    const [key, , , opts] = field;
    const node = advancedEngineForm.elements.namedItem(key);
    if (!node || !(key in di)) continue;
    if (opts?.type === "checkbox") node.checked = Boolean(di[key]);
    else node.value = di[key];
  }
  $("#advancedCaseLabel").textContent =
    preset.status && preset.status !== "available" ? `${preset.name} · ${preset.status}` : preset.name;
}

function readAdvancedInput() {
  const config = advancedEngineConfigs[selectedEngine];
  const data = { ...config.defaults };
  for (const field of config.fields) {
    const [key, , , opts] = field;
    const node = advancedEngineForm.elements.namedItem(key);
    if (!node) continue;
    if (opts?.type === "checkbox") {
      data[key] = node.checked;
    } else if (opts?.type === "select") {
      data[key] = node.value;
    } else if (node.value !== "") {
      data[key] = Number(node.value);
    }
  }
  return data;
}

function renderAdvancedSweepControls(config) {
  const select = $("#advancedSweepParameter");
  const values = $("#advancedSweepValues");
  if (!select || !values) return;
  select.replaceChildren();
  for (const [key, label] of config.sweepParameters || []) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = label;
    if (config.sweepDefault?.parameter === key) option.selected = true;
    select.append(option);
  }
  if (config.sweepDefault) values.value = config.sweepDefault.values;
}

function updateAdvancedMetrics(result) {
  animateMetric($("#advancedThrustValue"), uval("thrust", result.thrust_kN, 2), result.thrust_kN);
  animateMetric($("#advancedTsfcValue"), uval("tsfc", result.TSFC_kg_per_kN_hr, 2), result.TSFC_kg_per_kN_hr);
  $("#advancedFarValue").textContent = numberFormat(result.fuel_air_ratio, 4);
  $("#advancedNozzleValue").textContent = result.nozzle_choked ? "Choked" : "Unchoked";
  $("#advancedSpecificThrustValue").textContent = uval("specthrust", result.specific_thrust_N_per_kg_s, 1);
  animateMetric($("#advancedOverallEtaValue"),
    `${numberFormat(result.overall_efficiency_estimate * 100, 1)} %`,
    result.overall_efficiency_estimate * 100);
  renderAdvancedDetail(result);
}

/* Engine-specific detail block, appears under the metric grid and lists the
 * physically meaningful per-engine outputs that the generic metric grid would
 * otherwise omit (core/bypass thrust for turbofans, shaft power for
 * turboprops, etc.). */
function renderAdvancedDetail(result) {
  const host = $("#advancedDetail");
  if (!host) return;
  const rows = [
    ["Thermal η", `${numberFormat(result.thermal_efficiency_estimate * 100, 1)} %`],
    ["Propulsive η", `${numberFormat(result.propulsive_efficiency_estimate * 100, 1)} %`],
    ["Fuel flow", uval("flow", result.fuel_flow_kg_s, 3)],
    ["Exit velocity", uval("vel", result.exit_velocity_m_s, 1)],
    ["Freestream V₀", uval("vel", result.freestream_velocity_m_s, 1)],
    ["Momentum thrust", uval("thrust", result.momentum_thrust_N / 1000, 2)],
    ["Pressure thrust", uval("thrust", result.pressure_thrust_N / 1000, 2)],
  ];
  if (result.core_thrust_N != null) {
    rows.push(["Core thrust", uval("thrust", result.core_thrust_N / 1000, 2)]);
  }
  if (result.bypass_thrust_N != null) {
    rows.push(["Bypass thrust", uval("thrust", result.bypass_thrust_N / 1000, 2)]);
  }
  if (result.bypass_exit_velocity_m_s != null) {
    rows.push(["Bypass V₁₉", uval("vel", result.bypass_exit_velocity_m_s, 1)]);
  }
  const xtra = result.extra || {};
  if (xtra.third_stream_active) {
    rows.push(["Cycle mode", xtra.variable_cycle_mode === "high_thrust" ? "High thrust" : "High efficiency"]);
    rows.push(["Third-stream thrust", uval("thrust", (result.third_stream_thrust_N || 0) / 1000, 2)]);
    rows.push(["Effective bypass ratio", numberFormat(xtra.effective_bypass_ratio, 2)]);
    rows.push(["Total ṁ air (w/ 3rd)", uval("flow", xtra.total_air_with_third_kg_s, 1)]);
  }
  if (result.afterburner_fuel_air_ratio != null && result.afterburner_fuel_air_ratio > 0) {
    rows.push(["AB fuel-air", numberFormat(result.afterburner_fuel_air_ratio, 4)]);
  }
  if (result.shaft_power_kW != null) {
    rows.push(["Shaft power", uval("power", result.shaft_power_kW, 1)]);
  }
  if (result.equivalent_shaft_power_kW != null) {
    rows.push(["Equivalent SHP", uval("power", result.equivalent_shaft_power_kW, 1)]);
  }
  if (result.BSFC_kg_per_kW_h != null) {
    rows.push(["BSFC", uval("bsfc", result.BSFC_kg_per_kW_h, 3)]);
  }
  if (result.propeller_thrust_N != null) {
    rows.push(["Propeller thrust", uval("thrust", result.propeller_thrust_N / 1000, 2)]);
  }
  if (result.jet_thrust_N != null) {
    rows.push(["Residual jet thrust", uval("thrust", result.jet_thrust_N / 1000, 2)]);
  }
  const extra = result.extra || {};
  if (extra.propeller_efficiency != null && extra.propeller_efficiency > 0) {
    rows.push(["η_prop", `${numberFormat(extra.propeller_efficiency * 100, 1)} %`]);
  }
  if (extra.advance_ratio != null && extra.advance_ratio > 0) {
    rows.push(["Advance ratio J", numberFormat(extra.advance_ratio, 2)]);
  }
  if (extra.propeller_tip_mach != null) {
    rows.push(["Prop tip Mach", numberFormat(extra.propeller_tip_mach, 2)]);
  }
  if (extra.applied_inlet_recovery != null) {
    rows.push(["Inlet recovery (applied)", numberFormat(extra.applied_inlet_recovery, 3)]);
  }
  if (extra.combustor_exit_mach_estimate != null) {
    rows.push(["Combustor exit M (est.)", numberFormat(extra.combustor_exit_mach_estimate, 2)]);
  }
  if (extra.ram_pressure_ratio != null) {
    rows.push(["Ram Pt/P₀", numberFormat(extra.ram_pressure_ratio, 1)]);
  }
  if (extra.Tt_rise_K != null) {
    rows.push(["Combustor ΔTt", `${numberFormat(extra.Tt_rise_K, 0)} K`]);
  }
  if (extra.bypass_ratio != null) {
    rows.push(["Bypass ratio", numberFormat(extra.bypass_ratio, 2)]);
  }
  if (extra.overall_pressure_ratio != null) {
    rows.push(["Overall pressure ratio", numberFormat(extra.overall_pressure_ratio, 1)]);
  }
  host.replaceChildren();
  for (const [k, v] of rows) {
    const row = document.createElement("div");
    row.className = "detail-row";
    const lhs = document.createElement("span");
    lhs.textContent = k;
    const rhs = document.createElement("strong");
    rhs.textContent = v;
    row.append(lhs, rhs);
    host.append(row);
  }
}

async function runAdvancedSimulation() {
  const config = advancedEngineConfigs[selectedEngine];
  const inputs = readAdvancedInput();
  const { errors, cautions } = collectGeometryProblems(inputs);
  if (errors.length) {
    updateAdvancedWarnings(errors);
    return undefined;
  }
  const result = await postJson(config.route, inputs);
  lastResult = result;
  updateAdvancedMetrics(result);
  updateAdvancedWarnings([...cautions, ...(result.warnings || [])]);
  fillStationTable(advancedStationTableBody, result.station_table);
  setActiveStation(Object.values(result.station_table)[0]?.station ?? 0);
  animateStationChart(result, advancedStationCanvas);
  updateGraphCanvases();
  $("#advancedCaseLabel").textContent = `${engineLabels[selectedEngine]} run`;
  return result;
}

/* ------------------------------------------------------------ *
 *  24. ENGINE SELECTION                                          *
 * ------------------------------------------------------------ */

function selectEngine(engineType) {
  const previousEngine = selectedEngine;
  selectedEngine = engineType;
  $("#engineModeLabel").textContent = engineLabels[engineType];
  if ($("#appTitle")) $("#appTitle").textContent = `${engineLabels[engineType]} cycle`;
  document.querySelectorAll(".engine-card").forEach((b) => {
    b.classList.toggle("active", b.dataset.engine === engineType);
  });
  $("#turbojetWorkspace").classList.toggle("hidden", engineType !== "turbojet");
  document.querySelector(".sweep-panel").classList.toggle("hidden", engineType !== "turbojet");
  const advSweep = document.querySelector(".advanced-sweep-panel");
  if (advSweep) advSweep.classList.toggle("hidden", engineType === "turbojet");
  $("#advancedEngineWorkspace").classList.toggle("hidden", engineType === "turbojet");
  $("#downloadReportButton").disabled = false;
  $("#downloadReportButton").textContent = `Download ${engineLabels[engineType].toLowerCase()} PDF`;
  $("#reportStatus").textContent = "";
  drawEngineCrossSection();
  if (engineType !== "turbojet") renderAdvancedInputs();
  // Drop the previous engine's cycle result so the Graphs tab does not show
  // stations from a different architecture (e.g. fan 13 / bypass 19 / LPT 45
  // bleeding into a turbojet view).
  if (previousEngine && previousEngine !== engineType) {
    lastResult = null;
    updateGraphCanvases();
  }
}

/* ------------------------------------------------------------ *
 *  25. RUN SIMULATION / SWEEP / COMPARE                          *
 * ------------------------------------------------------------ */

async function runSimulation() {
  const inputs = readFormInput();
  const { errors, cautions } = collectGeometryProblems(inputs);
  if (errors.length) {
    updateWarnings(errors);
    return undefined;
  }
  const result = await postJson("/simulate/turbojet", inputs);
  lastResult = result;
  updateMetrics(result);
  updateWarnings([...cautions, ...(result.warnings || [])]);
  updateNozzlePanel(result);
  updateStationTable(result.station_table);
  setActiveStation(3);
  animateStationChart(result);
  updateGraphCanvases();
  updateHeroTelemetry(result, inputs);
  updateCycleInsights(result, inputs);
  updateEmissions(result);
  $("#caseLabel").textContent = "Latest run";
  return result;
}

/* ---------------- Reactor-network combustor emissions ----------------
 * After each turbojet run, post the combustor-inlet state (station 3) and the
 * core fuel-air ratio to /emissions/combustor and show the Cantera NOx / CO
 * emission indices. The "Estimate ICAO LTO NOx" button runs the engine-coupled
 * landing-takeoff aggregation off the current deck. */
async function updateEmissions(result) {
  const note = document.getElementById("emissionsNote");
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  const t3 = result?.station_table?.[3];
  const far = result?.core_fuel_air_ratio ?? result?.fuel_air_ratio;
  if (!t3 || !far) return;
  try {
    const emis = await postJson("/emissions/combustor", {
      combustor_inlet_temperature_K: t3.stagnation_temperature_K,
      combustor_inlet_pressure_Pa: t3.stagnation_pressure_Pa,
      fuel_air_ratio: Math.min(0.074, Math.max(1e-4, far)),
    });
    const fmt = (v, d = 1) =>
      Number.isFinite(Number(v)) ? Number(v).toLocaleString(undefined, { maximumFractionDigits: d }) : ", ";
    set("eiNoxValue", fmt(emis.ei_nox_g_per_kg, 1));
    set("eiCoValue", fmt(emis.ei_co_g_per_kg, 2));
    set("flameTempValue", emis.primary_zone_temperature_K ? fmt(emis.primary_zone_temperature_K, 0) : ", ");
    set("phiOverallValue", fmt(emis.phi_overall, 2));
    if (note) {
      const src = emis.source === "reactor-network"
        ? "Two-zone Cantera reactor network (Zeldovich NO)."
        : "P3–T3 correlation (Cantera unavailable).";
      note.textContent = `${src} EI = grams pollutant per kg fuel.`;
    }
  } catch (err) {
    if (note) note.textContent = `Emissions unavailable: ${err.message}`;
  }
}

async function estimateLtoNox() {
  const host = document.getElementById("ltoResult");
  const button = document.getElementById("ltoButton");
  if (!host) return;
  const inputs = readFormInput();
  if (button) { button.disabled = true; button.textContent = "Estimating…"; }
  try {
    const out = await postJson("/emissions/turbojet/lto", { design: inputs });
    const fmt = (v, d = 1) =>
      Number.isFinite(Number(v)) ? Number(v).toLocaleString(undefined, { maximumFractionDigits: d }) : ", ";
    const rows = out.modes.map((m) =>
      `<tr><td>${m.name}</td><td>${fmt(m.thrust_fraction * 100, 0)}%</td>` +
      `<td>${fmt(m.combustor_inlet_temperature_K, 0)}</td>` +
      `<td>${fmt(m.ei_nox_g_per_kg, 1)}</td><td>${fmt(m.fuel_flow_kg_s, 2)}</td>` +
      `<td>${fmt(m.nox_g, 0)}</td></tr>`).join("");
    host.innerHTML =
      `<p class="insight-sub">Rated thrust <strong>${uval("thrust", out.rated_thrust_kN, 1)}</strong> · ` +
      `Dp(NOx) <strong>${fmt(out.dp_nox_g, 0)} g</strong> · ` +
      `Dp/Foo <strong>${fmt(out.dp_foo_g_per_kN, 1)} g/kN</strong></p>` +
      `<table><thead><tr><th>Mode</th><th>F00</th><th>T₃ [K]</th><th>EI NOx</th>` +
      `<th>Wf [kg/s]</th><th>NOx [g]</th></tr></thead><tbody>${rows}</tbody></table>` +
      (out.notes?.length ? `<p class="insight-sub">${out.notes[0]}</p>` : "");
    host.hidden = false;
  } catch (err) {
    host.innerHTML = `<p class="insight-sub">LTO estimate failed: ${err.message}</p>`;
    host.hidden = false;
  } finally {
    if (button) { button.disabled = false; button.textContent = "Estimate ICAO LTO NOx →"; }
  }
}

/* ---------------- NSGA-II design optimization ----------------
 * Trace the Pareto front of (min TSFC, max specific thrust) over compressor
 * pressure ratio and turbine-inlet temperature, at the Cycle-tab flight
 * condition, and draw it as a scatter on the optimize canvas. */
let lastPareto = null;

async function runOptimization() {
  const status = document.getElementById("optStatus");
  const button = document.getElementById("optRun");
  const num = (id, d) => { const v = Number(document.getElementById(id)?.value); return Number.isFinite(v) ? v : d; };
  if (button) { button.disabled = true; button.textContent = "Optimizing…"; }
  if (status) status.textContent = "Running NSGA-II… (this evaluates the cycle thousands of times)";
  try {
    const out = await postJson("/optimize/turbojet", {
      design: readFormInput(),
      tt3_max_K: num("optTt3Max", 950),
      population_size: Math.round(num("optPop", 40)),
      generations: Math.round(num("optGen", 40)),
      seed: 0,
    });
    lastPareto = out;
    const fmt = (v, d = 1) =>
      Number.isFinite(Number(v)) ? Number(v).toLocaleString(undefined, { maximumFractionDigits: d }) : ", ";
    const front = out.pareto_front;
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    set("optFrontSize", String(front.length));
    set("optEvals", fmt(out.evaluations, 0));
    set("optMinTsfc", uval("tsfc", Math.min(...front.map((p) => p.TSFC_kg_per_kN_hr)), 1));
    set("optMaxSpec", uval("specthrust", Math.max(...front.map((p) => p.specific_thrust_N_per_kg_s)), 0));
    drawParetoFront(out);
    if (status) status.textContent =
      `Pareto front: ${front.length} non-dominated designs from ${fmt(out.evaluations, 0)} cycle evaluations.`;
  } catch (err) {
    if (status) status.textContent = `Optimization failed: ${err.message}`;
  } finally {
    if (button) { button.disabled = false; button.textContent = "Run optimization"; }
  }
}

function drawParetoFront(out) {
  const canvas = document.getElementById("optimizeCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const front = out.pareto_front;
  if (!front.length) return;

  const pad = { l: 64, r: 18, t: 18, b: 48 };
  const xs = front.map((p) => p.TSFC_kg_per_kN_hr);
  const ys = front.map((p) => p.specific_thrust_N_per_kg_s);
  let xmin = Math.min(...xs), xmax = Math.max(...xs);
  let ymin = Math.min(...ys), ymax = Math.max(...ys);
  const xpad = (xmax - xmin) * 0.08 || 1, ypad = (ymax - ymin) * 0.08 || 1;
  xmin -= xpad; xmax += xpad; ymin -= ypad; ymax += ypad;
  const px = (v) => pad.l + ((v - xmin) / (xmax - xmin)) * (W - pad.l - pad.r);
  const py = (v) => H - pad.b - ((v - ymin) / (ymax - ymin)) * (H - pad.t - pad.b);

  // Axes
  ctx.strokeStyle = "rgba(255,255,255,0.18)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, H - pad.b); ctx.lineTo(W - pad.r, H - pad.b);
  ctx.stroke();
  ctx.fillStyle = "rgba(255,255,255,0.55)";
  ctx.font = "11px ui-monospace, monospace";
  ctx.fillText("TSFC  [kg/kN·h]  →", pad.l, H - 16);
  ctx.save();
  ctx.translate(16, pad.t + 8); ctx.rotate(-Math.PI / 2);
  ctx.fillText("Specific thrust  [N·s/kg]  →", 0, 0);
  ctx.restore();

  // Connecting line (front is sorted by TSFC ascending).
  ctx.strokeStyle = "rgba(123,167,235,0.45)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  front.forEach((p, i) => {
    const X = px(p.TSFC_kg_per_kN_hr), Y = py(p.specific_thrust_N_per_kg_s);
    if (i === 0) ctx.moveTo(X, Y); else ctx.lineTo(X, Y);
  });
  ctx.stroke();

  // Points coloured by turbine-inlet temperature (cool→hot).
  front.forEach((p) => {
    const X = px(p.TSFC_kg_per_kN_hr), Y = py(p.specific_thrust_N_per_kg_s);
    const t = (p.turbine_inlet_temperature_K - 1100) / (1800 - 1100);
    const hue = 210 - Math.max(0, Math.min(1, t)) * 190;   // blue → red
    ctx.fillStyle = `hsl(${hue}, 70%, 60%)`;
    ctx.beginPath(); ctx.arc(X, Y, 3.4, 0, Math.PI * 2); ctx.fill();
  });
}

/* ---------------- Live cycle-insights interpreter ----------------
 * Turns the raw simulation numbers into 4-6 plain-English bullet points the
 * student can use to actually learn what is going on in the cycle. Updates
 * after every run. Anything ambiguous is omitted rather than guessed. */
function updateCycleInsights(result, inputs) {
  const host = document.getElementById("cycleInsights");
  if (!host || !result) return;
  const bullets = [];
  const t0 = result.station_table?.[0] || {};
  const t3 = result.station_table?.[3] || {};
  const t4 = result.station_table?.[4] || {};
  const t5 = result.station_table?.[5] || {};
  const npr = result.nozzle_pressure_ratio;
  const exp = (result.nozzle_expansion_status || "").toLowerCase();
  const fmt = (v, d = 1) =>
    Number.isFinite(Number(v))
      ? Number(v).toLocaleString(undefined, { maximumFractionDigits: d })
      : ", ";

  // Compressor exit temperature
  if (t3.stagnation_temperature_K) {
    const Tt3 = t3.stagnation_temperature_K;
    if (Tt3 > 850) {
      bullets.push(
        `Compressor exit Tt3 is <b>${fmt(Tt3, 0)} K</b>, high enough that the back stages would need cooling on a real engine. Compressor work scales with this rise from Tt2.`
      );
    } else {
      bullets.push(
        `Compressor lifts the air from <b>${fmt(t0.stagnation_temperature_K || 0, 0)} K</b> at the freestream to <b>${fmt(Tt3, 0)} K</b> at station 3, that temperature rise is the work the turbine has to supply.`
      );
    }
  }
  // Nozzle choking
  if (result.nozzle_choked) {
    bullets.push(
      `Nozzle is <b>choked</b> (M=1 at the throat). That happens whenever Pt₅/P₀ exceeds the critical pressure ratio (~1.89 for hot gas), here Pt₅/P₀ = <b>${fmt(npr, 2)}</b>.`
    );
  } else {
    bullets.push(
      `Nozzle is <b>not choked</b> at this operating point (Pt₅/P₀ = ${fmt(npr, 2)}). The flow accelerates only to subsonic exit and produces less momentum thrust than a choked design.`
    );
  }
  // Nozzle expansion state
  if (exp.includes("under")) {
    bullets.push(
      `Exit is <b>under-expanded</b>, exit static pressure exceeds ambient, so the gas keeps expanding outside the nozzle. A longer divergent section would recover some of that pressure thrust.`
    );
  } else if (exp.includes("over")) {
    bullets.push(
      `Exit is <b>over-expanded</b>, exit pressure is below ambient, costing some momentum to ambient back-pressure. A smaller exit area would match better at this flight condition.`
    );
  } else if (exp.includes("ideal")) {
    bullets.push(
      `Nozzle is <b>nearly ideally expanded</b>, exit static pressure matches ambient, which maximises momentum thrust for the given Pt.`
    );
  }
  // TSFC interpretation
  const tsfc = result.TSFC_kg_per_kN_hr;
  if (Number.isFinite(tsfc)) {
    let comment;
    if (tsfc < 90) comment = "very good, turbofan-class economy";
    else if (tsfc < 150) comment = "typical for a simple turbojet cycle";
    else if (tsfc < 250) comment = "high, likely low TIT or low PR";
    else comment = "very high, check inputs or expect afterburner-class numbers";
    bullets.push(
      `TSFC ≈ <b>${fmt(tsfc, 1)} kg/(kN·hr)</b>, ${comment}. Lower is better; ramjets typically sit above 200, modern high-bypass turbofans around 50–60.`
    );
  }
  // Efficiency hint
  if (Number.isFinite(result.thermal_efficiency_estimate)) {
    bullets.push(
      `Thermal η ≈ <b>${fmt(result.thermal_efficiency_estimate * 100, 1)}%</b>, propulsive η ≈ <b>${fmt(result.propulsive_efficiency_estimate * 100, 1)}%</b>. Overall η ≈ thermal × propulsive for a pure-jet engine, try raising PR or TIT and watch thermal rise.`
    );
  }
  // Fuel-air sanity
  if (Number.isFinite(result.fuel_air_ratio)) {
    const f = result.fuel_air_ratio;
    if (f < 0.008 || f > 0.055) {
      bullets.push(
        `Fuel-air ratio <b>${fmt(f, 4)}</b> is outside the typical lean turbojet band of 0.015–0.040, check TIT vs compressor exit.`
      );
    }
  }
  host.replaceChildren();
  for (const html of bullets.slice(0, 6)) {
    const li = document.createElement("li");
    li.innerHTML = html;
    host.append(li);
  }
}

/* Info-pop click toggle (touch-friendly). Hover already works via :hover. */
document.addEventListener("click", (e) => {
  const pop = e.target.closest(".info-pop");
  document.querySelectorAll(".info-pop.open").forEach((p) => {
    if (p !== pop) p.classList.remove("open");
  });
  if (pop) {
    pop.classList.toggle("open");
    e.preventDefault();
  }
});

/* Concept-strip "Read manual →" CTA jumps to the manual tab. */
document.addEventListener("click", (e) => {
  const cta = e.target.closest("[data-jump-tab]");
  if (!cta) return;
  e.preventDefault();
  const tabName = cta.getAttribute("data-jump-tab");
  document.querySelectorAll(".tab-button").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.dataset.tabPanel === tabName);
  });
  document.querySelector(".console-tabs")?.scrollIntoView({ behavior: "smooth", block: "start" });
});

/* ---------------- Live hero-telemetry binding ----------------
 * Wire the six ghost readouts in the pressure-contour SVG to the most recent
 * turbojet simulation. Falls back gracefully (preserves the em-dash) when a
 * value is missing. Called after every simulation and once on page boot. */
function updateHeroTelemetry(result, inputs) {
  const t0 = result?.station_table?.[0];
  const t4 = result?.station_table?.[4];
  const fmt = (v, d = 1) =>
    Number.isFinite(Number(v))
      ? Number(v).toLocaleString(undefined, { maximumFractionDigits: d })
      : ", ";
  const setText = (id, text) => {
    const node = document.getElementById(id);
    if (node) node.textContent = text;
  };
  setText("pcTelMach", `M  ${fmt(inputs?.mach, 2)}`);
  setText("pcTelT0",   `T₀ ${uval("temp", t0?.static_temperature_K, 0)}`);
  setText("pcTelP0",   `P₀ ${uval("press", t0?.static_pressure_Pa / 1000, 1)}`);
  setText("pcTelTt",   `Tₜ ${uval("temp", t4?.stagnation_temperature_K, 0)}`);
  setText("pcTelPt",   `Pₜ ${uval("press", t4?.stagnation_pressure_Pa / 1000, 0)}`);
  setText("pcTelEta",  `η_th ${fmt(result?.thermal_efficiency_estimate, 2)}`);
}

async function runSweep() {
  const rawValues = $("#sweepValues").value
    .split(",").map((v) => Number(v.trim())).filter((v) => !Number.isNaN(v));
  const payload = await postJson("/simulate/turbojet/sweep", {
    base_input: readFormInput(),
    sweep_parameter: $("#sweepParameter").value,
    values: rawValues,
  });
  lastSweepPayload = payload;
  drawSweepChart(payload);
  $("#sweepSummary").textContent =
    `${payload.summary.successful_cases} succeeded · ${payload.summary.failed_cases} failed · ` +
    `peak thrust ${uval("thrust", payload.summary.max_thrust_N / 1000, 2)} · ` +
    `min TSFC ${uval("tsfc", payload.summary.min_TSFC_kg_per_kN_hr, 2)}`;
  updateSweepExplanation(payload);
  updateGraphCanvases();
}

function renderCompareCards(cases) {
  const container = $("#compareCards");
  container.replaceChildren();
  for (const comparison of cases) {
    const card = document.createElement("article");
    card.className = "compare-card";
    const title = document.createElement("h3");
    title.textContent = comparison.label;
    const lines = [
      ["Thrust", uval("thrust", comparison.result.thrust_kN, 2)],
      ["TSFC", uval("tsfc", comparison.result.TSFC_kg_per_kN_hr, 2)],
      ["Fuel-air ratio", numberFormat(comparison.result.fuel_air_ratio, 4)],
      ["Nozzle", comparison.result.nozzle_choked ? "Choked" : "Not choked"],
      ["Station 4 Tt", `${numberFormat(comparison.result.station_table["4"]?.stagnation_temperature_K, 1)} K`],
    ];
    card.append(title);
    for (const [label, value] of lines) {
      const row = document.createElement("div");
      row.className = "compare-row";
      const labelNode = document.createElement("span");
      labelNode.textContent = label;
      const valueNode = document.createElement("b");
      valueNode.textContent = value;
      row.append(labelNode, valueNode);
      card.append(row);
    }
    container.append(card);
  }
}

function drawCompareChart(cases) {
  const { context: ctx, width, height } = canvasScale(compareCanvas);
  ctx.clearRect(0, 0, width, height);
  const pad = 48;
  drawChartFrame(ctx, pad, pad, width - pad * 2, height - pad * 2);

  if (!cases.length) {
    ctx.fillStyle = palette.textDim;
    ctx.font = "500 12px 'Inter', system-ui";
    ctx.fillText("Run compare to populate this chart", pad + 8, pad + 22);
    return;
  }
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  const maxThrust = Math.max(...cases.map((e) => e.result.thrust_kN));
  const maxTsfc = Math.max(...cases.map((e) => e.result.TSFC_kg_per_kN_hr));

  cases.forEach((entry, i) => {
    const slot = plotW / cases.length;
    const x0 = pad + i * slot + slot * 0.18;
    const thrustH = (entry.result.thrust_kN / maxThrust) * plotH;
    const tsfcH = (entry.result.TSFC_kg_per_kN_hr / maxTsfc) * plotH;

    ctx.fillStyle = palette.thrust;
    ctx.fillRect(x0, pad + plotH - thrustH, slot * 0.22, thrustH);
    ctx.fillStyle = palette.tsfc;
    ctx.fillRect(x0 + slot * 0.28, pad + plotH - tsfcH, slot * 0.22, tsfcH);

    ctx.fillStyle = palette.textDim;
    ctx.font = "500 11px 'Inter', system-ui";
    ctx.textAlign = "center";
    ctx.fillText(entry.label, x0 + slot * 0.22, height - 16);
    ctx.textAlign = "left";
  });

  drawSeriesLabel(ctx, "Thrust  [kN]", pad + 4, pad - 14, palette.thrust);
  drawSeriesLabel(ctx, "TSFC  [kg/kN/hr]", pad + 110, pad - 14, palette.tsfc);
}

async function runCompare() {
  /* Build a spec list from the user's checkbox selection. The turbojet entry
   * uses the current form input; every other family uses its baseline
   * defaults from `advancedEngineConfigs`. The backend handles solver dispatch
   * via /compare/engines. */
  const specs = [];
  if ($("#compareIncludeTurbojet")?.checked) {
    specs.push({
      label: "Turbojet (current)",
      engine_type: "turbojet",
      turbojet_input: readFormInput(),
    });
  }
  for (const family of ["turbofan", "turboprop", "ramjet", "scramjet"]) {
    const box = $(`#compareInclude${family[0].toUpperCase()}${family.slice(1)}`);
    if (box?.checked) {
      const cfg = advancedEngineConfigs[family];
      specs.push({
        label: `${engineLabels[family]} baseline`,
        engine_type: family,
        [`${family}_input`]: { ...cfg.defaults },
      });
    }
  }
  if (specs.length < 2) {
    $("#compareWarnings").textContent = "Select at least two engines to compare.";
    renderCompareCards([]);
    drawCompareChart([]);
    return;
  }
  const payload = await postJson("/compare/engines", { specs });
  const cases = payload.cases.map((c) => ({
    label: c.label,
    success: c.success,
    error: c.error,
    result: c.success
      ? {
          thrust_kN: c.thrust_kN,
          TSFC_kg_per_kN_hr: c.TSFC_kg_per_kN_hr,
          fuel_air_ratio: c.fuel_air_ratio,
          nozzle_choked: c.nozzle_choked,
          thermal_efficiency_estimate: c.thermal_efficiency_estimate,
          propulsive_efficiency_estimate: c.propulsive_efficiency_estimate,
          overall_efficiency_estimate: c.overall_efficiency_estimate,
          engine_type: c.engine_type,
          station_table: {},  // not returned by /compare/engines
        }
      : null,
  }));
  renderCompareCards(cases);
  drawCompareChart(cases.filter((c) => c.success));
  $("#compareWarnings").textContent = payload.warnings?.join("  ·  ") || "";
}

async function runAdvancedSweep() {
  const config = advancedEngineConfigs[selectedEngine];
  if (!config) return;
  const rawValues = $("#advancedSweepValues").value
    .split(",").map((v) => Number(v.trim())).filter((v) => !Number.isNaN(v));
  const payload = await postJson(config.sweepRoute, {
    base_input: readAdvancedInput(),
    sweep_parameter: $("#advancedSweepParameter").value,
    values: rawValues,
  });
  drawAdvancedSweepChart(payload);
  const s = payload.summary;
  $("#advancedSweepSummary").textContent =
    `${s.successful_cases} succeeded · ${s.failed_cases} failed · ` +
    `peak thrust ${uval("thrust", s.max_thrust_N / 1000, 2)} · ` +
    `min TSFC ${uval("tsfc", s.min_TSFC_kg_per_kN_hr, 2)}`;
}

function drawAdvancedSweepChart(payload) {
  const canvas = $("#advancedSweepCanvas");
  if (!canvas) return;
  const { context: ctx, width, height } = canvasScale(canvas);
  ctx.clearRect(0, 0, width, height);
  const pad = 48;
  drawChartFrame(ctx, pad, pad, width - pad * 2, height - pad * 2);

  const successful = payload.cases.filter((c) => c.success);
  if (!successful.length) {
    ctx.fillStyle = palette.textDim;
    ctx.font = "500 12px 'Inter', system-ui";
    ctx.fillText("Sweep produced no successful cases.", pad + 8, pad + 22);
    return;
  }
  const xs = successful.map((c) => c.input_value);
  const thrustKN = successful.map((c) => c.output.thrust_kN);
  const tsfc = successful.map((c) => c.output.TSFC_kg_per_kN_hr);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const tMin = Math.min(...thrustKN);
  const tMax = Math.max(...thrustKN);
  const sMin = Math.min(...tsfc);
  const sMax = Math.max(...tsfc);
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  const xToPx = (x) => pad + ((x - xMin) / Math.max(xMax - xMin, 1e-9)) * plotW;
  const tToPx = (t) => pad + plotH - ((t - tMin) / Math.max(tMax - tMin, 1e-9)) * plotH;
  const sToPx = (s) => pad + plotH - ((s - sMin) / Math.max(sMax - sMin, 1e-9)) * plotH;

  ctx.strokeStyle = palette.thrust;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  successful.forEach((c, i) => {
    const x = xToPx(c.input_value), y = tToPx(c.output.thrust_kN);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.strokeStyle = palette.tsfc;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  successful.forEach((c, i) => {
    const x = xToPx(c.input_value), y = sToPx(c.output.TSFC_kg_per_kN_hr);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // x-axis ticks
  ctx.fillStyle = palette.textDim;
  ctx.font = "500 11px 'Inter', system-ui";
  ctx.textAlign = "center";
  xs.forEach((x) => {
    ctx.fillText(numberFormat(x, 2), xToPx(x), pad + plotH + 18);
  });
  ctx.textAlign = "left";
  drawSeriesLabel(ctx, "Thrust [kN]", pad + 4, pad - 14, palette.thrust);
  drawSeriesLabel(ctx, "TSFC [kg/kN/hr]", pad + 120, pad - 14, palette.tsfc);
  ctx.fillStyle = palette.textDim;
  ctx.fillText(payload.sweep_parameter, pad + plotW / 2 - 40, pad + plotH + 36);
}

/* ------------------------------------------------------------ *
 *  26. PDF REPORT                                                *
 * ------------------------------------------------------------ */

async function downloadPdfReport() {
  const route = selectedEngine === "turbojet" ? "/reports/turbojet/pdf" : `/reports/${selectedEngine}/pdf`;
  const body = selectedEngine === "turbojet" ? readFormInput() : readAdvancedInput();
  $("#reportStatus").textContent = `Building ${engineLabels[selectedEngine].toLowerCase()} PDF…`;
  const response = await fetch(route, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(formatRequestError(payload.detail, "Could not generate PDF report"));
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `propulsionlab-${selectedEngine}-report.pdf`;
  link.style.display = "none";
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  $("#reportStatus").textContent = `${engineLabels[selectedEngine]} PDF generated.`;
}

/* Export the current console state as a standalone, runnable Python API-client
 * script (stdlib only). The script POSTs the same inputs to the same endpoint
 * the UI uses, so it reproduces the current numbers. */
async function exportPythonScript() {
  const isTurbojet = selectedEngine === "turbojet";
  const inputs = isTurbojet ? readFormInput() : readAdvancedInput();
  const engineType = isTurbojet ? inputs.engine_variant : selectedEngine;
  $("#reportStatus").textContent = "Generating Python script…";
  const response = await fetch("/export/python", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ engine_type: engineType, inputs }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(formatRequestError(payload.detail, "Could not generate Python script"));
  }
  const text = await response.text();
  const blob = new Blob([text], { type: "text/x-python" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `propulsionlab_${engineType}.py`;
  link.style.display = "none";
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  $("#reportStatus").textContent = `Python script for ${engineLabels[selectedEngine].toLowerCase()} downloaded.`;
}

/* ------------------------------------------------------------ *
 *  27. EVENT LISTENERS                                           *
 * ------------------------------------------------------------ */

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try { await runSimulation(); }
  catch (error) { updateWarnings([error.message]); }
});

advancedEngineForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try { await runAdvancedSimulation(); }
  catch (error) { updateAdvancedWarnings([error.message]); }
});

document.querySelectorAll(".engine-card").forEach((button) => {
  button.addEventListener("click", async () => {
    selectEngine(button.dataset.engine);
    try {
      if (selectedEngine === "turbojet") {
        await runSimulation();
        await runSweep();
      } else {
        await runAdvancedSimulation();
      }
    } catch (error) {
      if (selectedEngine === "turbojet") updateWarnings([error.message]);
      else updateAdvancedWarnings([error.message]);
    }
  });
});

$("#resetButton").addEventListener("click", async () => {
  populateForm(currentPresetInput);
  await runSimulation();
});
$("#advancedResetButton").addEventListener("click", async () => {
  renderAdvancedInputs();
  await runAdvancedSimulation();
});

presetSelect.addEventListener("change", async () => {
  applyPreset(presetSelect.value);
  await runSimulation();
  await runSweep();
});

const advancedPresetEl = document.getElementById("advancedPresetSelect");
if (advancedPresetEl) advancedPresetEl.addEventListener("change", async () => {
  applyAdvancedPreset(advancedPresetEl.value);
  await runAdvancedSimulation();
});

const ltoButtonEl = document.getElementById("ltoButton");
if (ltoButtonEl) ltoButtonEl.addEventListener("click", () => { estimateLtoNox(); });

const optRunEl = document.getElementById("optRun");
if (optRunEl) optRunEl.addEventListener("click", () => { runOptimization(); });

/* ---------------- Sensitivity (tornado chart) ----------------
 * Perturb each Cycle-tab input by ±delta, post to /analyze/turbojet/sensitivity,
 * and draw a tornado: longest bars = inputs the output cares about most. The
 * metric delta is shown in the active unit system. */
const SENS_METRIC_UNIT = {
  thrust_kN: { kind: "thrust" },
  TSFC_kg_per_kN_hr: { kind: "tsfc" },
  specific_thrust_N_per_kg_s: { kind: "specthrust" },
  overall_efficiency_estimate: { kind: null, scale: 100, unit: "pp" },
};
let lastSensitivity = null;

function sensConvertDelta(metricKey, delta) {
  if (delta == null) return null;
  const m = SENS_METRIC_UNIT[metricKey];
  if (!m) return delta;
  return m.kind ? unitConvert(m.kind, delta) : delta * (m.scale || 1);
}
function sensDeltaUnit(metricKey) {
  const m = SENS_METRIC_UNIT[metricKey];
  if (!m) return "";
  return m.kind ? unitLabel(m.kind) : (m.unit || "");
}
function sensFmtBaseline(metricKey, value) {
  const m = SENS_METRIC_UNIT[metricKey];
  if (m && m.kind) return uval(m.kind, value, 2);
  if (m) return `${numberFormat(value * (m.scale || 1), 1)} ${m.unit || ""}`;
  return numberFormat(value, 2);
}

async function runSensitivity() {
  const status = document.getElementById("sensStatus");
  const button = document.getElementById("sensRun");
  const metric = document.getElementById("sensMetric")?.value || "thrust_kN";
  const pct = Number(document.getElementById("sensDelta")?.value) || 10;
  if (button) { button.disabled = true; button.textContent = "Running…"; }
  if (status) status.textContent = "Perturbing each input…";
  try {
    const out = await postJson("/analyze/turbojet/sensitivity", {
      design: readFormInput(),
      metric,
      delta_fraction: Math.min(Math.max(pct / 100, 0.01), 0.5),
    });
    lastSensitivity = out;
    drawTornado(out);
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    set("sensBaseline", sensFmtBaseline(out.metric, out.base_metric));
    set("sensTop", out.rows.length ? out.rows[0].label : "—");
    if (status) status.textContent =
      `${out.metric_label} ranked across ${out.rows.length} inputs at ±${Math.round(out.delta_fraction * 100)}%.`;
  } catch (err) {
    if (status) status.textContent = `Sensitivity failed: ${err.message}`;
  } finally {
    if (button) { button.disabled = false; button.textContent = "Run sensitivity"; }
  }
}

function drawTornado(out) {
  const canvas = document.getElementById("sensitivityCanvas");
  if (!canvas) return;
  const { context: ctx, width: W, height: H } = canvasScale(canvas);
  ctx.clearRect(0, 0, W, H);
  const metric = out.metric;
  const conv = (d) => sensConvertDelta(metric, d);
  const rows = (out.rows || []).filter((r) => r.delta_low != null || r.delta_high != null);
  if (!rows.length) {
    ctx.fillStyle = "#8b9099"; ctx.font = "12px -apple-system, system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.fillText("No sensitivity to show.", W / 2, H / 2);
    return;
  }
  let maxAbs = 0;
  for (const r of rows) for (const d of [conv(r.delta_low), conv(r.delta_high)]) {
    if (d != null) maxAbs = Math.max(maxAbs, Math.abs(d));
  }
  if (maxAbs <= 0) maxAbs = 1;

  const padL = 118, padR = 58, padT = 16, padB = 38;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const cx = padL + plotW / 2;
  const X = (d) => cx + (d / maxAbs) * (plotW / 2);
  const rowH = plotH / rows.length;
  const barH = Math.min(16, rowH * 0.46);

  // baseline axis
  ctx.strokeStyle = "rgba(255,255,255,0.28)"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(cx, padT); ctx.lineTo(cx, padT + plotH); ctx.stroke();

  ctx.font = "11px -apple-system, system-ui, sans-serif";
  rows.forEach((r, i) => {
    const yc = padT + rowH * (i + 0.5);
    ctx.fillStyle = "#c8ccd2"; ctx.textAlign = "right"; ctx.textBaseline = "middle";
    ctx.fillText(r.label, padL - 10, yc);
    const drawBar = (delta, color) => {
      const d = conv(delta); if (d == null) return;
      const x = X(d), x0 = Math.min(cx, x), w = Math.max(1, Math.abs(x - cx));
      ctx.fillStyle = color;
      ctx.fillRect(x0, yc - barH / 2, w, barH);
    };
    drawBar(r.delta_high, "rgba(123,167,235,0.85)"); // input raised → blue
    drawBar(r.delta_low, "rgba(240,136,62,0.85)");   // input lowered → amber
  });

  // x ticks + axis title
  ctx.fillStyle = "#8b9099"; ctx.textAlign = "center"; ctx.textBaseline = "top";
  ctx.font = "10px ui-monospace, monospace";
  for (const frac of [-1, -0.5, 0, 0.5, 1]) {
    const d = frac * maxAbs;
    ctx.fillText(`${d > 0 ? "+" : ""}${numberFormat(d, 1)}`, X(d), padT + plotH + 6);
  }
  ctx.font = "11px -apple-system, system-ui, sans-serif";
  ctx.fillText(`Δ ${out.metric_label} (${sensDeltaUnit(metric)})`, cx, H - 13);
}

function initSensitivity() {
  if (!lastSensitivity) runSensitivity().catch(() => {});
  else drawTornado(lastSensitivity);
}

const sensRunEl = document.getElementById("sensRun");
if (sensRunEl) sensRunEl.addEventListener("click", () => { runSensitivity(); });
const sensMetricEl = document.getElementById("sensMetric");
if (sensMetricEl) sensMetricEl.addEventListener("change", () => { runSensitivity(); });

/* ---------------- Transient spool dynamics ----------------
 * Slam the throttle and integrate the rotor equation of motion; the spool (and
 * thrust) lag the fuel. Plots spool speed % and thrust against time, with the
 * commanded-spool step shown dashed so the lag is visible. */
let lastTransient = null;

async function runTransient() {
  const status = document.getElementById("trStatus");
  const button = document.getElementById("trRun");
  const num = (id, d) => { const v = Number(document.getElementById(id)?.value); return Number.isFinite(v) ? v : d; };
  if (button) { button.disabled = true; button.textContent = "Running…"; }
  if (status) status.textContent = "Calibrating the operating line and integrating the spool…";
  try {
    const idle = Math.min(Math.max(num("trIdle", 70) / 100, 0.4), 0.95);
    const command = Math.min(Math.max(num("trCommand", 100) / 100, 0.4), 1.0);
    const total = Math.min(Math.max(num("trTime", 8), 2), 30);
    const out = await postJson("/simulate/turbojet/transient", {
      design: readFormInput(),
      polar_moment_of_inertia_kg_m2: Math.min(Math.max(num("trInertia", 20), 1), 200),
      idle_throttle_fraction: idle,
      command_throttle_fraction: command,
      slam_time_s: Math.min(1.0, total * 0.1),
      total_time_s: total,
      dt_s: total > 16 ? 0.06 : 0.04,
    });
    lastTransient = out;
    drawTransient(out);
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    const s = out.samples;
    set("trTau", `${numberFormat(out.tau0_s, 2)} s`);
    set("trSettle", out.settling_time_s == null ? "—" : `${numberFormat(out.settling_time_s, 2)} s`);
    set("trIdleThrust", uval("thrust", s[0].thrust_kN, 2));
    set("trFinalThrust", uval("thrust", s[s.length - 1].thrust_kN, 2));
    if (status) status.textContent =
      `Slam ${Math.round(idle * 100)}% → ${Math.round(command * 100)}% Tt₄. Spool τ₀ = ${numberFormat(out.tau0_s, 2)} s.`;
  } catch (err) {
    if (status) status.textContent = `Transient failed: ${err.message}`;
  } finally {
    if (button) { button.disabled = false; button.textContent = "Run transient"; }
  }
}

function drawTransient(out) {
  const canvas = document.getElementById("transientCanvas");
  if (!canvas) return;
  const { context: ctx, width: W, height: H } = canvasScale(canvas);
  ctx.clearRect(0, 0, W, H);
  const s = out.samples || [];
  if (s.length < 2) return;

  const padL = 48, padR = 52, padT = 16, padB = 34;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const tMax = s[s.length - 1].t_s || 1;
  // spool axis in %
  const spoolVals = s.flatMap((p) => [p.spool_fraction, p.spool_target]);
  let nMin = Math.min(...spoolVals), nMax = Math.max(...spoolVals);
  nMin = Math.max(0, nMin - (nMax - nMin) * 0.12 - 0.02);
  nMax = nMax + (nMax - nMin) * 0.05 + 0.01;
  // thrust axis (converted)
  const thr = s.map((p) => unitConvert("thrust", p.thrust_kN));
  const thrMax = Math.max(...thr) * 1.12 || 1;

  const X = (t) => padL + (t / tMax) * plotW;
  const Yn = (n) => padT + plotH - ((n - nMin) / (nMax - nMin)) * plotH;
  const Yt = (v) => padT + plotH - (v / thrMax) * plotH;

  // grid + frame
  ctx.strokeStyle = "rgba(255,255,255,0.06)"; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (plotH * i) / 4;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke();
  }

  const line = (fn, color, dash) => {
    ctx.beginPath();
    ctx.setLineDash(dash || []);
    s.forEach((p, i) => { const x = X(p.t_s), y = fn(p); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.stroke();
    ctx.setLineDash([]);
  };
  // commanded spool (dashed grey), actual spool (blue), thrust (amber)
  line((p) => Yn(p.spool_target), "rgba(180,186,196,0.5)", [5, 4]);
  line((p) => Yn(p.spool_fraction), "#7ba7eb");
  line((p) => Yt(unitConvert("thrust", p.thrust_kN)), "#f0883e");

  // axes labels + ticks
  ctx.fillStyle = "#8b9099"; ctx.font = "10px ui-monospace, monospace";
  ctx.textAlign = "right"; ctx.textBaseline = "middle";
  for (let i = 0; i <= 4; i++) {
    const n = nMin + ((nMax - nMin) * (4 - i)) / 4;
    ctx.fillText(`${Math.round(n * 100)}`, padL - 5, padT + (plotH * i) / 4);
  }
  ctx.textAlign = "left"; ctx.fillStyle = "rgba(240,136,62,0.9)";
  for (let i = 0; i <= 4; i++) {
    const v = (thrMax * (4 - i)) / 4;
    ctx.fillText(`${numberFormat(v, 0)}`, W - padR + 5, padT + (plotH * i) / 4);
  }
  ctx.fillStyle = "#8b9099"; ctx.textAlign = "center"; ctx.textBaseline = "top";
  for (let i = 0; i <= 5; i++) {
    const t = (tMax * i) / 5;
    ctx.fillText(`${numberFormat(t, 1)}`, X(t), padT + plotH + 6);
  }
  ctx.font = "11px -apple-system, system-ui, sans-serif";
  ctx.fillStyle = "#7ba7eb"; ctx.fillText("spool % N", padL + 30, 4);
  ctx.fillStyle = "rgba(240,136,62,0.9)"; ctx.textAlign = "right";
  ctx.fillText(`thrust ${unitLabel("thrust")}`, W - padR, 4);
  ctx.fillStyle = "#8b9099"; ctx.textAlign = "center";
  ctx.fillText("time (s)", padL + plotW / 2, H - 12);
}

function initTransient() {
  if (!lastTransient) runTransient().catch(() => {});
  else drawTransient(lastTransient);
}

const trRunEl = document.getElementById("trRun");
if (trRunEl) trRunEl.addEventListener("click", () => { runTransient(); });

$("#saveProfileButton").addEventListener("click", () => { saveCurrentProfile(); });
$("#loadProfileButton").addEventListener("click", async () => {
  if (loadCustomProfile()) { await runSimulation(); await runSweep(); }
});
$("#deleteProfileButton").addEventListener("click", () => { deleteCustomProfile(); });

$("#runSweepButton").addEventListener("click", async () => {
  try { await runSweep(); }
  catch (error) { $("#sweepSummary").textContent = error.message; }
});

$("#downloadReportButton").addEventListener("click", async () => {
  try { await downloadPdfReport(); }
  catch (error) {
    $("#reportStatus").textContent = error.message;
    if (selectedEngine === "turbojet") updateWarnings([error.message]);
    else updateAdvancedWarnings([error.message]);
  }
});

$("#exportPythonButton")?.addEventListener("click", async () => {
  try { await exportPythonScript(); }
  catch (error) { $("#reportStatus").textContent = error.message; }
});

$("#exportStationCsvButton").addEventListener("click", () => {
  if (lastResult?.station_table) exportStationCsv(lastResult.station_table, "propulsionlab-stations.csv");
});
$("#exportAdvancedStationCsvButton").addEventListener("click", () => {
  if (lastResult?.station_table) {
    exportStationCsv(lastResult.station_table, `propulsionlab-${selectedEngine}-stations.csv`);
  }
});
$("#shareLinkButton")?.addEventListener("click", (e) => copyShareLink(e.currentTarget));
$("#shareAdvancedLinkButton")?.addEventListener("click", (e) => copyShareLink(e.currentTarget));

$("#runAdvancedSweepButton")?.addEventListener("click", async () => {
  try { await runAdvancedSweep(); }
  catch (err) {
    $("#advancedSweepSummary").textContent = `Error: ${err.message}`;
  }
});

$("#runCompareButton").addEventListener("click", async () => {
  try { await runCompare(); }
  catch (error) { $("#compareCards").textContent = error.message; }
});

engineViewerCanvas.addEventListener("mousemove", (event) => {
  const rect = engineViewerCanvas.getBoundingClientRect();
  const px = event.clientX - rect.left;
  const py = event.clientY - rect.top;
  const hit = engineViewerHitRegions.find(
    (r) => px >= r.x0 && px <= r.x1 && py >= r.y0 && py <= r.y1,
  );
  engineViewerCanvas.style.cursor = hit?.station ? "pointer" : "default";
  if (hit?.station && Number(hit.station) !== Number(activeStation)) {
    setActiveStation(hit.station);
  }
});

form.addEventListener("input", (event) => {
  const field = event.target;
  if (field instanceof HTMLInputElement || field instanceof HTMLSelectElement) {
    field.classList.toggle("input-invalid", !field.validity.valid);
  }
});

document.querySelectorAll(".tab-button").forEach((button) => {
  button.addEventListener("click", () => {
    const tab = button.dataset.tab;
    document.querySelectorAll(".tab-button").forEach((item) => {
      item.classList.toggle("active", item.dataset.tab === tab);
    });
    document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.tabPanel === tab);
    });
    if (tab === "graphs") updateGraphCanvases();
    else if (tab === "compare") drawCompareChart([]);
    else if (tab === "offdesign") initOffDesign();
    else if (tab === "mission") initMission();
    else if (tab === "compressormap") initCompressorMap();
    else if (tab === "sensitivity") initSensitivity();
    else if (tab === "transient") initTransient();
  });
});

/* Scroll-reveal: each main .section fades + rises into view the first time it
 * enters the viewport. IntersectionObserver-driven, GPU-composited, one-shot
 * (unobserved after first reveal). Content is only hidden once JS confirms it
 * can reveal it, so no-JS users see everything. Reduced-motion shows all
 * sections immediately. */
function initScrollReveal() {
  const sections = Array.from(document.querySelectorAll(".app-shell .section"));
  if (!sections.length) return;
  if (prefersReducedMotion || !("IntersectionObserver" in window)) {
    sections.forEach((s) => s.classList.add("reveal", "in-view"));
    return;
  }
  sections.forEach((s) => s.classList.add("reveal"));
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          observer.unobserve(entry.target);
        }
      }
    },
    { rootMargin: "0px 0px -12% 0px", threshold: 0.08 },
  );
  sections.forEach((s) => observer.observe(s));
}
initScrollReveal();

/* Activate a console tab by name, keeps the tab-button + tab-panel pair in sync. */
function activateConsoleTab(tabName) {
  document.querySelectorAll(".tab-button").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.dataset.tabPanel === tabName);
  });
}

document.getElementById("heroLaunchButton")?.addEventListener("click", () => {
  activateConsoleTab("dashboard");
  document.querySelector(".console-tabs")?.scrollIntoView({ behavior: "smooth", block: "start" });
});

document.getElementById("heroSweepButton")?.addEventListener("click", async () => {
  // Make sure we are on the dashboard tab + turbojet so the sweep panel is visible.
  activateConsoleTab("dashboard");
  if (selectedEngine !== "turbojet") selectEngine("turbojet");
  const target = document.querySelector(".sweep-panel");
  if (target) {
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    // Briefly highlight to draw the eye.
    target.classList.add("flash-attention");
    setTimeout(() => target.classList.remove("flash-attention"), 1400);
  }
  // Trigger the sweep so the visualisation actually populates.
  try {
    await runSweep();
  } catch (err) {
    const summary = document.getElementById("sweepSummary");
    if (summary) summary.textContent = `Sweep failed: ${err.message}`;
  }
});

let resizeTimer = null;
window.addEventListener("resize", () => {
  if (resizeTimer) window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    drawEngineCrossSection();
    if (lastResult) {
      if (selectedEngine === "turbojet") drawStationChart(lastResult);
      else drawStationChart(lastResult, advancedStationCanvas);
    }
    updateGraphCanvases();
  }, 220);
});

/* ------------------------------------------------------------ *
 *  28. BOOT (no overlay, direct fade-in via CSS)                *
 * ------------------------------------------------------------ */

async function boot() {
  animateHeroCounters();
  initUnitToggle();
  try {
    const response = await fetch("/api");
    if (!response.ok) throw new Error("API unavailable");
    setStatus("Online", "ok");
    await loadPresets();
    refreshCustomProfiles();
    // If the URL carries a shared scenario, restore it; otherwise boot the
    // default turbojet cycle + sweep.
    const shared = readSharedStateFromUrl();
    if (shared && (await applySharedState(shared))) {
      if (selectedEngine === "turbojet") await runSweep();
    } else {
      selectEngine("turbojet");
      await runSimulation();
      await runSweep();
    }
  } catch (error) {
    setStatus("Offline", "bad");
    updateWarnings([error.message]);
    // Still draw the static viewer with no result so the page isn't empty.
    drawEngineCrossSection();
  }
}

/* Remove the boot screen from the DOM once its CSS fade-out completes so it
 * can never intercept pointer events. Reduced-motion collapses the animation,
 * so pull it almost immediately in that case. */
(function removeBootScreen() {
  const boot = document.getElementById("bootScreen");
  if (!boot) return;
  const delay = prefersReducedMotion ? 60 : 1550;
  setTimeout(() => boot.remove(), delay);
})();

boot();

/* ------------------------------------------------------------ *
 *  29. OFF-DESIGN MATCHING PANEL (Day 13)                        *
 * ------------------------------------------------------------ *
 * Fetches a matched operating LINE once (a throttle sweep at a fixed flight
 * condition) from /simulate/{engine}/off-design, then lets a throttle slider
 * scrub thrust / TSFC / pressure-ratio along it by LOCAL linear interpolation,  * no network call per drag, so it updates far faster than 30 Hz. */

const offDesign = {
  engine: "turbojet",
  throttles: [], thrust: [], tsfc: [], pr: [], converged: [],
  min: 0, max: 1, ready: false,
};

/* Representative design point per engine; designTt4 is the top of the throttle
 * sweep (the calibration point), minTt4 the bottom. */
function offDesignSpec(engine, altitude_m, mach) {
  if (engine === "turbofan") {
    return {
      design: {
        altitude_m, mach, total_mass_flow_air_kg_s: 350,
        bypass_ratio: 6, fan_pressure_ratio: 1.6,
        core_compressor_pressure_ratio: 22, turbine_inlet_temperature_K: 1600,
      },
      designTt4: 1600, minTt4: 1300,
    };
  }
  return {
    design: {
      altitude_m, mach, mass_flow_air_kg_s: 60,
      compressor_pressure_ratio: 16, turbine_inlet_temperature_K: 1500,
    },
    designTt4: 1500, minTt4: 1150,
  };
}

async function computeOffDesignEnvelope() {
  const engine = $("#odEngine").value;
  const altitude_m = Number($("#odAltitude").value);
  const mach = Number($("#odMach").value);
  const spec = offDesignSpec(engine, altitude_m, mach);

  const N = 41;
  const throttles = [];
  for (let i = 0; i < N; i += 1) {
    throttles.push(spec.minTt4 + ((spec.designTt4 - spec.minTt4) * i) / (N - 1));
  }

  $("#odStatus").textContent = "Computing matched operating line…";
  let payload;
  try {
    payload = await postJson(`/simulate/${engine}/off-design`, {
      design: spec.design,
      grid: { throttles_K: throttles },
    });
  } catch (err) {
    $("#odStatus").textContent = `Could not compute envelope: ${err.message}`;
    return;
  }

  const ok = payload.points.filter((p) => p.success);
  if (!ok.length) {
    offDesign.ready = false;
    $("#odThrottle").disabled = true;
    $("#odStatus").textContent = "No matched points at this condition, try a lower altitude or Mach.";
    return;
  }

  offDesign.engine = engine;
  offDesign.throttles = ok.map((p) => p.turbine_inlet_temperature_K);
  offDesign.thrust = ok.map((p) => p.thrust_kN);
  offDesign.tsfc = ok.map((p) => p.TSFC_kg_per_kN_hr);
  offDesign.pr = ok.map((p) =>
    engine === "turbofan" ? p.overall_pressure_ratio : p.compressor_pressure_ratio,
  );
  offDesign.converged = ok.map((p) => p.converged);
  offDesign.min = offDesign.throttles[0];
  offDesign.max = offDesign.throttles[offDesign.throttles.length - 1];
  offDesign.ready = true;

  $("#odPrLabel").textContent = engine === "turbofan" ? "Overall PR" : "Compressor PR";
  const slider = $("#odThrottle");
  slider.disabled = false;
  slider.value = 100; // start at the design throttle

  const s = payload.summary;
  $("#odStatus").textContent =
    `${s.successful} matched · ${s.failed} dropped · ` +
    `peak ${uval("thrust", s.max_thrust_kN, 1)} · ` +
    `min TSFC ${uval("tsfc", s.min_TSFC_kg_per_kN_hr, 1)}`;

  updateOffDesignFromSlider();
}

/* Linear interpolation of the operating-line arrays at throttle t. */
function interpOffDesign(t) {
  const xs = offDesign.throttles;
  let i = 0;
  while (i < xs.length - 1 && xs[i + 1] < t) i += 1;
  const j = Math.min(i + 1, xs.length - 1);
  const f = xs[j] > xs[i] ? (t - xs[i]) / (xs[j] - xs[i]) : 0;
  const lerp = (a) => a[i] + (a[j] - a[i]) * f;
  return {
    thrust: lerp(offDesign.thrust),
    tsfc: lerp(offDesign.tsfc),
    pr: lerp(offDesign.pr),
    converged: offDesign.converged[f < 0.5 ? i : j],
  };
}

function updateOffDesignFromSlider() {
  if (!offDesign.ready) return;
  const pct = Number($("#odThrottle").value) / 100;
  const t = offDesign.min + (offDesign.max - offDesign.min) * pct;
  const v = interpOffDesign(t);
  $("#odThrottleValue").textContent = uval("temp", t, 0);
  $("#odThrust").textContent = uval("thrust", v.thrust, 2);
  $("#odTsfc").textContent = uval("tsfc", v.tsfc, 2);
  $("#odPr").textContent = numberFormat(v.pr, 2);
  $("#odConverged").textContent = v.converged ? "Yes" : ", ";
  drawOffDesignChart(t);
}

function drawOffDesignChart(markerT) {
  const canvas = $("#offDesignCanvas");
  if (!canvas || !offDesign.ready) return;
  const { context: ctx, width, height } = canvasScale(canvas);
  ctx.clearRect(0, 0, width, height);
  const pad = 48;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  drawChartFrame(ctx, pad, pad, plotW, plotH);

  const xs = offDesign.throttles;
  const xMin = offDesign.min;
  const xMax = offDesign.max;
  const tMin = Math.min(...offDesign.thrust);
  const tMax = Math.max(...offDesign.thrust);
  const sMin = Math.min(...offDesign.tsfc);
  const sMax = Math.max(...offDesign.tsfc);
  const xToPx = (x) => pad + ((x - xMin) / Math.max(xMax - xMin, 1e-9)) * plotW;
  const tToPx = (v) => pad + plotH - ((v - tMin) / Math.max(tMax - tMin, 1e-9)) * plotH;
  const sToPx = (v) => pad + plotH - ((v - sMin) / Math.max(sMax - sMin, 1e-9)) * plotH;

  // Throttle marker.
  if (markerT != null) {
    const mx = xToPx(markerT);
    ctx.strokeStyle = palette.accent;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(mx, pad);
    ctx.lineTo(mx, pad + plotH);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Thrust curve.
  ctx.strokeStyle = palette.thrust;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  xs.forEach((x, i) => {
    const px = xToPx(x);
    const py = tToPx(offDesign.thrust[i]);
    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  });
  ctx.stroke();

  // TSFC curve.
  ctx.strokeStyle = palette.tsfc;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  xs.forEach((x, i) => {
    const px = xToPx(x);
    const py = sToPx(offDesign.tsfc[i]);
    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  });
  ctx.stroke();

  // Marker dots at the interpolated point.
  if (markerT != null) {
    const v = interpOffDesign(markerT);
    ctx.fillStyle = palette.thrust;
    ctx.beginPath();
    ctx.arc(xToPx(markerT), tToPx(v.thrust), 3.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = palette.tsfc;
    ctx.beginPath();
    ctx.arc(xToPx(markerT), sToPx(v.tsfc), 3.2, 0, Math.PI * 2);
    ctx.fill();
  }

  // x-axis ticks.
  ctx.fillStyle = palette.textDim;
  ctx.font = "500 11px 'Inter', system-ui";
  ctx.textAlign = "center";
  const ticks = 5;
  for (let k = 0; k <= ticks; k += 1) {
    const x = xMin + ((xMax - xMin) * k) / ticks;
    ctx.fillText(numberFormat(x, 0), xToPx(x), pad + plotH + 18);
  }
  ctx.textAlign = "left";
  drawSeriesLabel(ctx, "Thrust [kN]", pad + 4, pad - 14, palette.thrust);
  drawSeriesLabel(ctx, "TSFC [kg/kN/hr]", pad + 120, pad - 14, palette.tsfc);
  ctx.fillStyle = palette.textDim;
  ctx.fillText("Throttle, turbine inlet T [K]", pad + plotW / 2 - 84, pad + plotH + 36);
}

let offDesignWired = false;
function initOffDesign() {
  if (!offDesignWired) {
    offDesignWired = true;
    $("#odCompute")?.addEventListener("click", () => {
      computeOffDesignEnvelope().catch(() => {});
    });
    $("#odThrottle")?.addEventListener("input", updateOffDesignFromSlider);
    $("#odEngine")?.addEventListener("change", () => {
      offDesign.ready = false;
      const slider = $("#odThrottle");
      if (slider) slider.disabled = true;
      // Default Mach hint: ramless turbojet vs cruise turbofan.
      $("#odStatus").textContent = "Press “Compute envelope” to match the operating line.";
    });
  }
  if (!offDesign.ready) computeOffDesignEnvelope().catch(() => {});
  else updateOffDesignFromSlider();
}

/* ------------------------------------------------------------ *
 *  30. MISSION PROFILE PANEL (Day 17)                           *
 * ------------------------------------------------------------ *
 * An editable waypoint table feeding POST /mission/{engine}. Editing any cell,
 * or adding/removing a leg, re-flies the mission (debounced) and updates the
 * totals + the fuel/altitude-vs-time chart. */

const mission = {
  segments: [
    { name: "climb",   altitude_m: 6000,  mach: 0.55, throttle_K: 1400, duration_s: 600 },
    { name: "cruise",  altitude_m: 10000, mach: 0.80, throttle_K: 1330, duration_s: 3600 },
    { name: "descent", altitude_m: 3000,  mach: 0.50, throttle_K: 1150, duration_s: 900 },
  ],
  lastResult: null,
};
let missionWired = false;
let missionFlyTimer = null;

const MISSION_COLUMNS = [
  ["name", "text"],
  ["altitude_m", "number"],
  ["mach", "number"],
  ["throttle_K", "number"],
  ["duration_s", "number"],
];

function renderMissionTable() {
  const body = $("#mnTableBody");
  if (!body) return;
  body.replaceChildren();
  mission.segments.forEach((seg, idx) => {
    const tr = document.createElement("tr");
    for (const [key, type] of MISSION_COLUMNS) {
      const td = document.createElement("td");
      const input = document.createElement("input");
      input.type = type;
      if (type === "number") input.step = "any";
      input.value = seg[key];
      input.className = "mn-cell";
      input.addEventListener("input", () => {
        seg[key] = type === "number" ? Number(input.value) : input.value;
        scheduleMissionFly();
      });
      td.append(input);
      tr.append(td);
    }
    // Fuel cell (read-only, filled from the last result).
    const fuelTd = document.createElement("td");
    fuelTd.className = "mn-fuel-cell";
    const row = mission.lastResult?.segments?.[idx];
    fuelTd.textContent = row && row.success ? numberFormat(row.fuel_burned_kg, 1)
      : (row && !row.success ? ", " : "");
    tr.append(fuelTd);
    // Remove button.
    const rmTd = document.createElement("td");
    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "mn-remove";
    rm.textContent = "✕";
    rm.title = "Remove leg";
    rm.disabled = mission.segments.length <= 1;
    rm.addEventListener("click", () => {
      mission.segments.splice(idx, 1);
      renderMissionTable();
      scheduleMissionFly();
    });
    rmTd.append(rm);
    tr.append(rmTd);
    body.append(tr);
  });
}

function addMissionSegment() {
  const last = mission.segments[mission.segments.length - 1] || {
    altitude_m: 10000, mach: 0.8, throttle_K: 1300, duration_s: 600,
  };
  mission.segments.push({
    name: `leg ${mission.segments.length + 1}`,
    altitude_m: last.altitude_m, mach: last.mach,
    throttle_K: last.throttle_K, duration_s: last.duration_s,
  });
  renderMissionTable();
  scheduleMissionFly();
}

function scheduleMissionFly() {
  if (missionFlyTimer) window.clearTimeout(missionFlyTimer);
  missionFlyTimer = window.setTimeout(() => flyMission().catch(() => {}), 400);
}

async function flyMission() {
  const engine = $("#mnEngine").value;
  $("#mnStatus").textContent = "Flying mission…";
  let result;
  try {
    result = await postJson(`/mission/${engine}`, {
      profile: { name: "Mission", segments: mission.segments },
    });
  } catch (err) {
    $("#mnStatus").textContent = `Could not fly mission: ${err.message}`;
    return;
  }
  mission.lastResult = result;
  $("#mnTotalFuel").textContent = `${numberFormat(result.total_fuel_kg, 1)} kg`;
  const mins = result.total_time_s / 60;
  $("#mnTotalTime").textContent = `${numberFormat(mins, 1)} min`;
  $("#mnMatched").textContent = `${result.successful_segments} / ${result.segments.length}`;
  $("#mnStatus").textContent = result.failed_segments
    ? `${result.failed_segments} leg(s) could not be matched, see the dashes in the table.`
    : "Mission matched at every leg.";
  renderMissionTable(); // refresh the fuel column
  drawMissionChart(result);
}

function drawMissionChart(result) {
  const canvas = $("#missionCanvas");
  if (!canvas) return;
  const { context: ctx, width, height } = canvasScale(canvas);
  ctx.clearRect(0, 0, width, height);
  const pad = 48;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  drawChartFrame(ctx, pad, pad, plotW, plotH);

  const segs = result.segments;
  const tMax = Math.max(result.total_time_s, 1);
  // Fuel series: piecewise-linear cumulative fuel vs cumulative time.
  const fuelMax = Math.max(result.total_fuel_kg || 0, 1);
  // Altitude series: held constant over each leg (step).
  const altMax = Math.max(...segs.map((s) => s.altitude_m), 1);

  const xToPx = (t) => pad + (t / tMax) * plotW;
  const fToPx = (f) => pad + plotH - (f / fuelMax) * plotH;
  const aToPx = (a) => pad + plotH - (a / altMax) * plotH;

  // Altitude step line.
  ctx.strokeStyle = palette.pressure;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  let tCursor = 0;
  segs.forEach((s, i) => {
    const x0 = xToPx(tCursor);
    const x1 = xToPx(tCursor + s.duration_s);
    const y = aToPx(s.altitude_m);
    if (i === 0) ctx.moveTo(x0, y); else ctx.lineTo(x0, y);
    ctx.lineTo(x1, y);
    tCursor += s.duration_s;
  });
  ctx.stroke();

  // Cumulative fuel line.
  ctx.strokeStyle = palette.thrust;
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  ctx.moveTo(xToPx(0), fToPx(0));
  let cum = 0;
  tCursor = 0;
  segs.forEach((s) => {
    tCursor += s.duration_s;
    if (s.success && s.cumulative_fuel_kg != null) cum = s.cumulative_fuel_kg;
    ctx.lineTo(xToPx(tCursor), fToPx(cum));
  });
  ctx.stroke();

  // Leg boundaries (faint verticals).
  ctx.strokeStyle = palette.grid;
  ctx.lineWidth = 1;
  tCursor = 0;
  segs.forEach((s) => {
    tCursor += s.duration_s;
    const x = xToPx(tCursor);
    ctx.beginPath();
    ctx.moveTo(x, pad);
    ctx.lineTo(x, pad + plotH);
    ctx.stroke();
  });

  drawSeriesLabel(ctx, "Cumulative fuel [kg]", pad + 4, pad - 14, palette.thrust);
  drawSeriesLabel(ctx, "Altitude [m]", pad + 168, pad - 14, palette.pressure);
  ctx.fillStyle = palette.textDim;
  ctx.font = "500 11px 'Inter', system-ui";
  ctx.fillText("Time [min]", pad + plotW / 2 - 28, pad + plotH + 30);
  ctx.textAlign = "center";
  for (let k = 0; k <= 4; k += 1) {
    const t = (tMax * k) / 4;
    ctx.fillText(numberFormat(t / 60, 0), xToPx(t), pad + plotH + 16);
  }
  ctx.textAlign = "left";
}

function initMission() {
  if (!missionWired) {
    missionWired = true;
    renderMissionTable();
    $("#mnAddSegment")?.addEventListener("click", addMissionSegment);
    $("#mnFly")?.addEventListener("click", () => flyMission().catch(() => {}));
    $("#mnEngine")?.addEventListener("change", () => flyMission().catch(() => {}));
  }
  if (!mission.lastResult) flyMission().catch(() => {});
  else drawMissionChart(mission.lastResult);
}

/* ------------------------------------------------------------ *
 *  31. COMPRESSOR MAP PANEL (Day 35 + 38)                       *
 * ------------------------------------------------------------ *
 * Plots pressure ratio vs corrected mass flow with constant
 * corrected-speed lines, surge/choke boundaries and a peak-
 * efficiency ridge, then overlays the matched OFF-DESIGN RUNNING
 * LINE and an operating-point marker. The map and the running
 * line both come from POST /simulate/turbojet/map-match, which
 * calibrates the current cycle deck, sizes a synthetic map to it,
 * and converges the operating point on the map at each throttle.
 * The throttle slider scrubs the marker along the matched line.
 * The map is synthetic (clearly labelled); a measured dataset
 * would load into the identical viewer. */

const compressorMap = { data: null, line: [], designIndex: 0, markerIndex: 0 };
let compressorMapWired = false;

/* Call the map-matching endpoint with the current cycle deck as the design
 * basis. Returns true on success. Turbojet only (the matching reference is a
 * dry turbojet); other architectures show a note. */
async function fetchMapMatch() {
  compressorMap.data = null;
  compressorMap.line = [];
  if (selectedEngine !== "turbojet") return false;
  const inputs = readFormInput();
  if (collectGeometryProblems(inputs).errors.length) return false;
  let result;
  try {
    result = await postJson("/simulate/turbojet/map-match", { design: inputs });
  } catch {
    return false;
  }
  compressorMap.data = result.compressor_map || null;
  compressorMap.line = Array.isArray(result.points) ? result.points : [];
  compressorMap.designIndex = result.design_index ?? 0;
  compressorMap.markerIndex = compressorMap.designIndex || 0;
  return Boolean(compressorMap.data);
}

function compressorMapBounds() {
  const d = compressorMap.data;
  if (!d) return null;
  let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
  for (let i = 0; i < d.speeds.length; i += 1) {
    for (let j = 0; j < d.beta.length; j += 1) {
      const x = d.mass_flow[i][j];
      const y = d.pressure_ratio[i][j];
      if (x < xMin) xMin = x;
      if (x > xMax) xMax = x;
      if (y < yMin) yMin = y;
      if (y > yMax) yMax = y;
    }
  }
  return { xMin, xMax, yMin, yMax };
}

function currentMarkerPoint() {
  const line = compressorMap.line;
  if (!line.length) return null;
  const i = Math.min(Math.max(compressorMap.markerIndex, 0), line.length - 1);
  return line[i];
}

function setCompressorMapReadout(point) {
  const pr = $("#cmPr"), md = $("#cmMdot"), ef = $("#cmEff");
  const sm = $("#cmSurge"), th = $("#cmThrust"), ir = $("#cmInRange");
  if (!point) {
    [pr, md, ef, sm, th, ir].forEach((n) => { if (n) n.textContent = ", "; });
    return;
  }
  if (pr) pr.textContent = numberFormat(point.pressure_ratio, 2);
  if (md) md.textContent = uval("flow", point.corrected_mass_flow, 1);
  if (ef) ef.textContent = `${numberFormat(point.efficiency * 100, 1)} %`;
  if (sm) sm.textContent = `${numberFormat(point.surge_margin * 100, 1)} %`;
  if (th) th.textContent = uval("thrust", point.thrust_kN, 2);
  if (ir) ir.textContent = point.in_range ? "Yes" : "Beyond map";
}

function updateCompressorMapStatus() {
  const el = $("#cmStatus");
  if (!el) return;
  if (selectedEngine !== "turbojet") {
    el.textContent =
      "Map matching is available for the dry turbojet in this release. Select the turbojet on the Cycle tab.";
  } else if (!compressorMap.line.length) {
    el.textContent =
      "Could not match a running line for this deck (afterburning, or the nozzle unchokes here). Try the dry turbojet or a higher altitude.";
  } else {
    el.textContent =
      "Off-design running line matched on the synthetic compressor map. Drag the throttle to move the operating point along the line.";
  }
}

function drawCompressorMap() {
  const canvas = $("#compressorMapCanvas");
  if (!canvas) return;
  const { context: ctx, width, height } = canvasScale(canvas);
  ctx.clearRect(0, 0, width, height);
  const pad = 52;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;

  const d = compressorMap.data;
  if (!d) {
    ctx.fillStyle = palette.textDim;
    ctx.font = "500 12px 'Inter', system-ui";
    ctx.textAlign = "center";
    ctx.fillText("No compressor map for this engine.", width / 2, height / 2);
    ctx.textAlign = "left";
    return;
  }

  const bounds = compressorMapBounds();
  let { xMin, xMax, yMin, yMax } = bounds;
  for (const p of compressorMap.line) {
    xMin = Math.min(xMin, p.corrected_mass_flow);
    xMax = Math.max(xMax, p.corrected_mass_flow);
    yMin = Math.min(yMin, p.pressure_ratio);
    yMax = Math.max(yMax, p.pressure_ratio);
  }
  const xPad = (xMax - xMin) * 0.08 || 1;
  const yPad = (yMax - yMin) * 0.08 || 1;
  xMin -= xPad; xMax += xPad; yMin -= yPad; yMax += yPad;
  const xToPx = (x) => pad + ((x - xMin) / (xMax - xMin)) * plotW;
  const yToPx = (y) => pad + plotH - ((y - yMin) / (yMax - yMin)) * plotH;

  drawChartFrame(ctx, pad, pad, plotW, plotH);

  const nb = d.beta.length;
  // Constant corrected-speed lines.
  d.speeds.forEach((sp, i) => {
    ctx.strokeStyle = palette.efficiency;
    ctx.globalAlpha = 0.5;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    d.beta.forEach((_, j) => {
      const px = xToPx(d.mass_flow[i][j]);
      const py = yToPx(d.pressure_ratio[i][j]);
      if (j === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    ctx.stroke();
    ctx.globalAlpha = 1;
    drawSeriesLabel(
      ctx,
      Number(sp).toFixed(2),
      xToPx(d.mass_flow[i][nb - 1]) - 2,
      yToPx(d.pressure_ratio[i][nb - 1]) - 4,
      palette.textDim,
    );
  });

  // Boundary helper: connect one beta column across all speed lines.
  const drawBoundary = (j, color, dash) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.4;
    ctx.setLineDash(dash);
    ctx.beginPath();
    d.speeds.forEach((_, i) => {
      const px = xToPx(d.mass_flow[i][j]);
      const py = yToPx(d.pressure_ratio[i][j]);
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    ctx.stroke();
    ctx.setLineDash([]);
  };
  drawBoundary(nb - 1, palette.temperature, [5, 4]); // surge line
  drawBoundary(0, palette.pressure, [2, 3]);         // choke line

  // Peak-efficiency ridge.
  ctx.strokeStyle = palette.efficiency;
  ctx.globalAlpha = 0.7;
  ctx.lineWidth = 1.1;
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  d.speeds.forEach((_, i) => {
    let best = 0;
    for (let j = 1; j < nb; j += 1) {
      if (d.efficiency[i][j] > d.efficiency[i][best]) best = j;
    }
    const px = xToPx(d.mass_flow[i][best]);
    const py = yToPx(d.pressure_ratio[i][best]);
    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  });
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;

  // Matched off-design running line.
  if (compressorMap.line.length) {
    ctx.strokeStyle = palette.accent;
    ctx.lineWidth = 2;
    ctx.beginPath();
    compressorMap.line.forEach((p, i) => {
      const px = xToPx(p.corrected_mass_flow);
      const py = yToPx(p.pressure_ratio);
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    ctx.stroke();
  }

  // Operating-point marker on the running line.
  const point = currentMarkerPoint();
  if (point) {
    const mx = xToPx(point.corrected_mass_flow);
    const my = yToPx(point.pressure_ratio);
    ctx.strokeStyle = palette.ink;
    ctx.globalAlpha = 0.5;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(mx - 9, my); ctx.lineTo(mx + 9, my); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(mx, my - 9); ctx.lineTo(mx, my + 9); ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.fillStyle = palette.accent;
    ctx.beginPath();
    ctx.arc(mx, my, 4.2, 0, Math.PI * 2);
    ctx.fill();
  }

  // Legend + axes.
  drawSeriesLabel(ctx, "Pressure ratio", pad + 4, pad - 30, palette.pressure);
  drawSeriesLabel(ctx, "surge", pad + 4, pad - 16, palette.temperature);
  drawSeriesLabel(ctx, "running line", pad + 64, pad - 16, palette.accent);
  ctx.fillStyle = palette.textDim;
  ctx.font = "500 11px 'Inter', system-ui";
  ctx.textAlign = "center";
  const ticks = 5;
  for (let k = 0; k <= ticks; k += 1) {
    const x = xMin + ((xMax - xMin) * k) / ticks;
    ctx.fillText(numberFormat(x, 0), xToPx(x), pad + plotH + 18);
  }
  ctx.fillText("Corrected mass flow [kg/s]", pad + plotW / 2, pad + plotH + 36);
  ctx.textAlign = "left";
}

function updateCompressorMapFromSlider() {
  const line = compressorMap.line;
  if (!line.length) return;
  const pct = Number($("#cmThrottle").value) / 100;
  compressorMap.markerIndex = Math.round(pct * (line.length - 1));
  const point = currentMarkerPoint();
  const out = $("#cmThrottleValue");
  if (out) out.textContent = point ? `${numberFormat(point.throttle_K, 0)} K` : ", ";
  setCompressorMapReadout(point);
  drawCompressorMap();
}

async function refreshCompressorMap() {
  const ok = await fetchMapMatch();
  const slider = $("#cmThrottle");
  const usable = ok && compressorMap.line.length > 0;
  if (slider) slider.disabled = !usable;
  updateCompressorMapStatus();
  if (usable) {
    const n = compressorMap.line.length;
    const frac = n > 1 ? compressorMap.designIndex / (n - 1) : 0;
    if (slider) slider.value = String(frac * 100);
    compressorMap.markerIndex = compressorMap.designIndex;
    const point = currentMarkerPoint();
    const out = $("#cmThrottleValue");
    if (out) out.textContent = point ? `${numberFormat(point.throttle_K, 0)} K` : ", ";
    setCompressorMapReadout(point);
  } else {
    setCompressorMapReadout(null);
    const out = $("#cmThrottleValue");
    if (out) out.textContent = ", ";
  }
  drawCompressorMap();
}

function initCompressorMap() {
  if (!compressorMapWired) {
    compressorMapWired = true;
    $("#cmRecenter")?.addEventListener("click", () => refreshCompressorMap().catch(() => {}));
    $("#cmThrottle")?.addEventListener("input", updateCompressorMapFromSlider);
  }
  refreshCompressorMap().catch(() => {});
}

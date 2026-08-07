/* =============================================================
   DAS LABS · PistonLab — console client
   A thin, live client on the Python crank-angle solver
   (POST /piston/simulate, /piston/sweep). The physics is the
   source of truth in app/engine_core/piston; this renders it.
   ============================================================= */

import { initBuilder, openBuilder } from "/lab/piston/builder.js?v=20260726-pl24";

const API_SIM = "/piston/simulate";
const API_SWEEP = "/piston/sweep";

/* Structured builder data — layout, cam and head have no form controls, so they
   live here and ride along with every solve until a different engine is built.
   The scalar answers go into the normal controls so they stay editable. */
let builderExtras = null;

/* ---------- units (SI solver, display-only conversion) ---------- */
const U = {
  power: { si: ["kW", 1e-3], us: ["hp", 1.34102209e-3] },     // from W
  torque: { si: ["N·m", 1], us: ["lb·ft", 0.737562149] },      // from N·m
  press: { si: ["bar", 1e-5], us: ["psi", 1.45037738e-4] },    // from Pa
  temp: { si: ["K", 1], us: ["°R", 1.8] },                     // from K
  bsfc: { si: ["g/kWh", 1], us: ["lb/hp·h", 0.0016439] },      // from g/kWh
  vol: { si: ["cm³", 1e6], us: ["in³", 6.1023744e4] },         // from m³
};
const UNIT_KEY = "pl_units";
let unit = localStorage.getItem(UNIT_KEY) === "US" ? "US" : "SI";
const ulabel = (k) => U[k][unit === "US" ? "us" : "si"][0];
const uconv = (k, v) => (v == null ? v : v * U[k][unit === "US" ? "us" : "si"][1]);
const fmt = (v, d = 1) =>
  v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d });
const uval = (k, v, d = 1) => `${fmt(uconv(k, v), d)} ${ulabel(k)}`;

/* ---------- input plumbing ---------- */
const STRING_KEYS = new Set(["fuel", "aspiration"]);
const INT_KEYS = new Set(["cylinders", "strokes_per_cycle"]);
const READOUT_DP = {
  equivalence_ratio: 2, combustion_efficiency: 3, compression_ratio: 1, rpm: 0,
  combustion_start_deg: 0, burn_duration_deg: 0, wall_heat_transfer_multiplier: 2,
  friction_multiplier: 2, intake_pressure_Pa: 2,
};

function readInputs() {
  const body = { include_trace: true };
  document.querySelectorAll("[data-key]").forEach((el) => {
    const key = el.dataset.key;
    if (STRING_KEYS.has(key)) { body[key] = el.value; return; }
    let v = parseFloat(el.value);
    if (Number.isNaN(v)) return;
    if (el.dataset.scale) v *= parseFloat(el.dataset.scale);
    if (INT_KEYS.has(key)) v = Math.round(v);
    body[key] = v;
  });
  if (builderExtras) Object.assign(body, builderExtras);
  return body;
}

/** Write one solver key into whichever control owns it, honouring its scale. */
function setKey(key, val) {
  const el = document.querySelector(`[data-key="${key}"]`);
  if (!el) return;
  if (STRING_KEYS.has(key)) el.value = val;
  else el.value = el.dataset.scale ? val / parseFloat(el.dataset.scale) : val;
}

/** Load a freshly built engine into the console and re-solve it. */
function applyBuiltEngine(spec, result) {
  // Bore and stroke come from the *server's* capacity solve, not a client-side
  // copy of the formula, so the console shows exactly what was simulated. They
  // land in millimetre fields, so round to 0.1 mm — the capacity shifts by a
  // fraction of a percent and the numbers stay something you could machine.
  const mm = (m) => Math.round(m * 1e4) / 1e4;
  setKey("bore_m", mm(result.bore_m));
  setKey("stroke_m", mm(result.stroke_m));
  for (const key of [
    "fuel", "cylinders", "strokes_per_cycle", "compression_ratio", "rod_ratio",
    "rpm", "equivalence_ratio", "combustion_start_deg", "burn_duration_deg",
    "aspiration", "intake_pressure_Pa", "intake_temperature_K",
  ]) {
    if (spec[key] !== undefined) setKey(key, spec[key]);
  }
  builderExtras = {
    layout: spec.layout,
    valve_timing: spec.valve_timing,
    valve_geometry: spec.valve_geometry,
  };
  document.querySelectorAll(".preset").forEach((b) => b.classList.remove("is-active"));
  updateReadouts();
  syncEngineType();
  solve();
}

function updateReadouts() {
  document.querySelectorAll("[data-readout]").forEach((b) => {
    const key = b.dataset.readout;
    const input = document.querySelector(`[data-key="${key}"]`);
    if (!input) return;
    const dp = READOUT_DP[key] ?? 1;
    b.textContent = fmt(parseFloat(input.value), dp);
  });
  const phiEl = document.querySelector('[data-key="equivalence_ratio"]');
  if (phiEl) {
    const phi = parseFloat(phiEl.value);
    const lam = 1 / phi;
    const tag = lam > 1.03 ? "lean" : lam < 0.97 ? "rich" : "stoichiometric";
    const foot = document.getElementById("lambdaFoot");
    if (foot) foot.textContent = `λ = ${fmt(lam, 2)} · ${tag}`;
  }
}

/* ---------- presets (knob bundles; Day 10 will formalise) ---------- */
const PRESETS = {
  "NA petrol I4": { fuel: "gasoline", compression_ratio: 11.0, bore_m: 0.086, stroke_m: 0.086, cylinders: 4, rpm: 4000, aspiration: "naturally_aspirated", intake_pressure_Pa: 1.0e5, equivalence_ratio: 1.0 },
  "Turbo petrol": { fuel: "gasoline", compression_ratio: 9.5, bore_m: 0.083, stroke_m: 0.092, cylinders: 4, rpm: 3500, aspiration: "turbocharged", intake_pressure_Pa: 1.8e5, intake_temperature_K: 320, equivalence_ratio: 1.0 },
  "Car diesel": { fuel: "diesel", compression_ratio: 18.0, bore_m: 0.085, stroke_m: 0.088, cylinders: 4, rpm: 3000, aspiration: "turbocharged", intake_pressure_Pa: 2.0e5, intake_temperature_K: 320, equivalence_ratio: 0.65, combustion_start_deg: -8 },
  "E85 turbo": { fuel: "ethanol", compression_ratio: 11.5, bore_m: 0.086, stroke_m: 0.086, cylinders: 4, rpm: 4000, aspiration: "turbocharged", intake_pressure_Pa: 2.0e5, intake_temperature_K: 320, equivalence_ratio: 1.0 },
};

function applyPreset(name) {
  const p = PRESETS[name];
  if (!p) return;
  // A stock preset replaces any bespoke layout/cam/head from the builder.
  builderExtras = null;
  const cfg = document.getElementById("configCard");
  if (cfg) cfg.hidden = true;
  for (const [key, val] of Object.entries(p)) {
    const el = document.querySelector(`[data-key="${key}"]`);
    if (!el) continue;
    if (STRING_KEYS.has(key)) el.value = val;
    else el.value = el.dataset.scale ? val / parseFloat(el.dataset.scale) : val;
  }
  document.querySelectorAll(".preset").forEach((b) => b.classList.toggle("is-active", b.dataset.preset === name));
  updateReadouts();
  syncEngineType();
  solve();
}

/* ---------- petrol / diesel engine type ---------- */
const familyOf = (fuel) => (fuel === "diesel" ? "diesel" : "petrol");
const ignitionOf = (fuel) => (fuel === "diesel" ? "compression" : "spark");
const TYPE_DEFAULTS = {
  petrol: { fuel: "gasoline", compression_ratio: 11.0, combustion_start_deg: -15, burn_duration_deg: 50,
            aspiration: "naturally_aspirated", intake_pressure_Pa: 1.0e5, intake_temperature_K: 330, equivalence_ratio: 1.0 },
  diesel: { fuel: "diesel", compression_ratio: 18.0, combustion_start_deg: -8, burn_duration_deg: 65,
            aspiration: "turbocharged", intake_pressure_Pa: 1.9e5, intake_temperature_K: 320, equivalence_ratio: 0.7 },
};

function applyEngineType(type) {
  const d = TYPE_DEFAULTS[type];
  if (!d) return;
  for (const [key, val] of Object.entries(d)) {
    const el = document.querySelector(`[data-key="${key}"]`);
    if (!el) continue;
    if (STRING_KEYS.has(key)) el.value = val;
    else el.value = el.dataset.scale ? val / parseFloat(el.dataset.scale) : val;
  }
  document.querySelectorAll(".preset").forEach((b) => b.classList.remove("is-active"));
  updateReadouts();
  syncEngineType();
  solve();
}

/** Reflect the current fuel into the type toggle, ignition badge and engine note. */
function syncEngineType() {
  const fuel = (document.querySelector('[data-key="fuel"]') || {}).value || "gasoline";
  const fam = familyOf(fuel), ign = ignitionOf(fuel);
  document.querySelectorAll(".etype").forEach((b) => b.classList.toggle("is-active", b.dataset.type === fam));
  const badge = document.getElementById("ignitionBadge");
  if (badge) { badge.dataset.ign = ign; badge.textContent = ign === "compression" ? "Compression" : "Spark"; }
  const note = document.getElementById("engineNote");
  if (note) note.textContent = ign === "compression"
    ? "A four-stroke diesel in motion. No spark plug — the injector sprays fuel into air compressed so hard it self-ignites. Charge colour tracks gas temperature; watch the marker trace the loops below."
    : "A four-stroke petrol engine in motion. The spark plug fires on your timing to light the mixture. Charge colour tracks gas temperature; watch the marker trace the loops below.";
}

/* ---------- view mode (enthusiast / engineer) ---------- */
const MODE_KEY = "pl_mode";
function setMode(m) {
  const mode = m === "engineer" ? "engineer" : "enthusiast";
  document.body.classList.remove("mode-enthusiast", "mode-engineer");
  document.body.classList.add(`mode-${mode}`);
  localStorage.setItem(MODE_KEY, mode);
  document.querySelectorAll(".mode-opt").forEach((b) => b.classList.toggle("is-active", b.dataset.mode === mode));
  requestAnimationFrame(() => { drawAllDiagrams(); drawDyno(); }); // re-measure newly shown charts
}

/* ---------- status ---------- */
function setStatus(text, cls) {
  const pill = document.getElementById("apiStatus");
  pill.textContent = text;
  pill.className = `status-pill ${cls || ""}`;
}

/* ---------- solve + render ---------- */
let lastResult = null;
let diagramMode = "loop"; // "loop" (P–V + T–s side by side) | "crank" (P–θ + T–θ)
let markerIdx = null;     // trace index for the engine-synced loop marker

/* Ghost trace: the loop as it stood *before* the edit you are making now, drawn
 * faintly behind the live one so a change is visible rather than remembered.
 *
 * It is deliberately not "the previous solve". Dragging a slider re-solves every
 * 180 ms, so the previous solve is almost the same shape and the ghost would be
 * invisible. Instead it is captured when a gesture *starts* — pointer down on a
 * control, a key press, a preset, a build — and held until the next gesture. So
 * it answers "what did this look like before I touched it", which is the
 * question you actually have while dragging. */
let ghostTrace = null;
let ghostArmed = false;   // guards against re-capturing mid-gesture

function armGhost() {
  if (ghostArmed) return;
  ghostArmed = true;
  ghostTrace = lastResult && Array.isArray(lastResult.trace) && lastResult.trace.length > 1
    ? lastResult.trace
    : null;
}
function disarmGhost() { ghostArmed = false; }

async function postJson(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const text = await res.text();
  let payload = {};
  try { payload = text ? JSON.parse(text) : {}; } catch { throw new Error(`Server error ${res.status}`); }
  if (!res.ok) {
    const d = payload?.detail;
    throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg || x).join("; ") : `Request failed (${res.status})`);
  }
  return payload;
}

let solveTimer = null;
function solveDebounced() {
  updateReadouts();
  clearTimeout(solveTimer);
  solveTimer = setTimeout(solve, 180);
}

async function solve() {
  setStatus("Solving", "busy");
  try {
    const r = await postJson(API_SIM, readInputs());
    lastResult = r;
    renderResult(r);
    setStatus("Solved", "ok");
  } catch (err) {
    setStatus(err.message.slice(0, 48) || "Error", "err");
  }
}

const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
const info = (tip) => `<span class="info" data-tip="${tip.replace(/"/g, "&quot;")}">i</span>`;

/* metric cards: persistent nodes with eased count-ups + ⓘ tooltips */
const METRICS = [
  { id: "mPower", label: "Brake power", cls: "primary", kind: "power", get: (r) => r.brake_power_W, dig: () => 1,
    tip: "Power delivered to the crankshaft after friction and pumping — what a dyno reads." },
  { id: "mTorque", label: "Brake torque", cls: "", kind: "torque", get: (r) => r.brake_torque_Nm, dig: () => 0,
    tip: "Turning effort at the crank: power ÷ rpm. Strong low-end torque is what you feel pulling away." },
  { id: "mBmep", label: "BMEP", cls: "", kind: "press", get: (r) => r.bmep_Pa, dig: () => 1,
    tip: "Brake mean effective pressure — torque normalised by engine size, so a 1L and a 6L compare directly. ~10 bar NA petrol, 20+ bar boosted." },
  { id: "mBsfc", label: "BSFC", cls: "", kind: "bsfc", get: (r) => r.bsfc_g_per_kWh, dig: () => (unit === "US" ? 3 : 0),
    tip: "Fuel burned per unit of work — lower is more efficient. ~250 g/kWh good petrol, ~200 diesel." },
];
const metricLive = {}, metricRAF = {};
function buildMetricCards() {
  document.getElementById("metricCards").innerHTML = METRICS.map((m) =>
    `<div class="metric ${m.cls}"><div class="k">${m.label}${info(m.tip)}</div><div class="v" id="${m.id}">—</div></div>`).join("");
}
function setMetric(id, target, digits, unitLabel) {
  const node = document.getElementById(id);
  if (!node) return;
  if (metricRAF[id]) cancelAnimationFrame(metricRAF[id]);
  const from = metricLive[id] !== undefined ? metricLive[id] : 0;
  const start = performance.now(), dur = 420;
  const step = (now) => {
    const t = Math.min(1, (now - start) / dur);
    const v = from + (target - from) * easeOutCubic(t);
    metricLive[id] = v;
    node.innerHTML = `${fmt(v, digits)}<span class="u">${unitLabel}</span>`;
    if (t < 1) metricRAF[id] = requestAnimationFrame(step);
    else { metricLive[id] = target; metricRAF[id] = null; }
  };
  metricRAF[id] = requestAnimationFrame(step);
}

function renderResult(r) {
  // metric cards (eased count-up)
  for (const m of METRICS) setMetric(m.id, uconv(m.kind, m.get(r)), m.dig(), ulabel(m.kind));

  // limit banner
  const banner = document.getElementById("limitBanner");
  banner.innerHTML = (r.operating_warnings || [])
    .map((w) => `<div class="limit ${w.severity}"><b>${w.kind.replace("_", " ")}</b><span>${w.message}</span></div>`)
    .join("");

  // breakdown ladder
  const rows = [];
  const pr = (label, v, cls = "") => rows.push(`<div class="row ${cls}"><span class="rk">${label}</span><span class="rv">${uval("press", v, 2)}</span></div>`);
  pr("Gross IMEP " + info("Indicated mean effective pressure — the work the gas does on the piston, before any losses are taken out."), r.imep_Pa);
  pr("− Pumping (PMEP)", r.pmep_Pa, "sub");
  pr("Net IMEP", r.net_imep_Pa);
  pr("− Friction (FMEP)", r.fmep_Pa, "sub");
  if (r.supercharger_power_W > 0) {
    rows.push(`<div class="row sub"><span class="rk">− Supercharger drive</span><span class="rv">${uval("power", r.supercharger_power_W, 1)}</span></div>`);
  }
  pr("BMEP " + info("Brake MEP: what's left at the crank after pumping and friction. This is the number that makes torque."), r.bmep_Pa, "total");
  const extra = (label, val) => rows.push(`<div class="row"><span class="rk">${label}</span><span class="rv">${val}</span></div>`);
  extra("Indicated power", uval("power", r.indicated_power_W, 1));
  extra("Mechanical efficiency", `${fmt(r.mechanical_efficiency * 100, 1)} %`);
  extra("Thermal efficiency (indicated)", `${fmt(r.thermal_efficiency * 100, 1)} %`);
  extra("Brake thermal efficiency", `${fmt(r.brake_thermal_efficiency * 100, 1)} %`);
  extra("Peak pressure", uval("press", r.peak_pressure_Pa, 1));
  extra("Peak temperature", uval("temp", r.peak_temperature_K, 0));
  if (r.fuel !== "manual") extra("Air-fuel ratio (λ)", `${fmt(r.air_fuel_ratio, 1)} (λ ${fmt(r.lambda_air, 2)})`);
  if (Math.abs(r.boost_pressure_Pa) > 1000) extra("Boost", uval("press", r.boost_pressure_Pa, 2));
  document.getElementById("breakdownRows").innerHTML = rows.join("");

  renderSummary(r);
  renderAnalysis(r);
  renderConfig(r);
  drawAllDiagrams();
}

/** Arrangement + breathing analysis. Only present once an engine is built. */
function renderConfig(r) {
  const card = document.getElementById("configCard");
  if (!card) return;
  const L = r.layout;
  const hasDepth = L || r.volumetric_efficiency != null
    || r.residual_fraction != null || r.turbine_pressure_ratio != null
    || r.mean_gamma != null;
  if (!hasDepth) { card.hidden = true; return; }
  card.hidden = false;

  // The Python side stays ASCII-only; the console is where it gets its degree sign.
  const pretty = (s) => String(s).replace(/ deg /g, "° ");
  document.getElementById("configName").textContent =
    L ? pretty(L.description) : r.volumetric_efficiency != null ? "custom valvetrain" : "gas model";

  const rows = [];
  const add = (label, val, tip) => rows.push(
    `<div class="row"><span class="rk">${label}${tip ? info(tip) : ""}</span><span class="rv">${val}</span></div>`);
  const group = (title) => rows.push(`<div class="row-group">${title}</div>`);

  if (L) {
    group("Architecture");
    add("Arrangement", pretty(L.description));
    add("Banks / heads", `${L.banks} × ${L.cylinders_per_bank}`);
    add("Crank throws", `${L.crank_throws} on ${L.main_bearings} mains`,
      "An opposed pair shares one throw station, which is why a flat-six runs fewer mains than an inline-six.");
    const gaps = [...new Set(L.firing_intervals_deg.map((g) => Math.round(g)))].join(" / ");
    add("Firing", `${L.even_fire ? "even" : "uneven"} · ${gaps}°`,
      `Ideal interval is 720°/${L.cylinders} = ${fmt(L.ideal_firing_interval_deg, 0)}°. A shared crankpin fires its pair one bank-angle apart, so only a bank angle equal to the ideal gives even firing.`);
    add("Friction scale", `${fmt(L.friction_scale, 3)}×`,
      "Coarse model correction for bearing and head count, anchored so an inline-four reads 1.000. A model parameter, not a measurement.");
  }
  if (r.effective_compression_ratio != null || r.volumetric_efficiency != null
      || r.residual_fraction != null || r.turbine_pressure_ratio != null
      || r.exhaust_temperature_K) {
    group("Breathing &amp; gas exchange");
  }
  if (r.effective_compression_ratio != null) {
    add("Effective CR", `${fmt(r.effective_compression_ratio, 2)}:1`,
      "V(IVC)/V_TDC — the ratio the trapped charge actually sees. Below the geometric ratio because the intake closes after BDC.");
    add("Expansion ratio", `${fmt(r.effective_expansion_ratio, 2)}:1`,
      "V(EVO)/V_TDC. When this exceeds the effective compression ratio the engine is running an Atkinson-style cycle.");
  }
  if (r.volumetric_efficiency != null) {
    add("Volumetric efficiency", `${fmt(r.volumetric_efficiency * 100, 1)} %`,
      "How much charge the head actually admits against what the cylinder could hold. Falls once the inlet starts choking.");
    add("Inlet Mach index", fmt(r.inlet_mach_index, 3),
      "Taylor's Z: the volume flow the piston demands over what the inlet valve can pass. Breathing falls away past about 0.5.");
    add("Exhaust Mach index", fmt(r.exhaust_mach_index, 3));
  }
  if (r.valve_overlap_deg != null) {
    add("Valve overlap", `${fmt(r.valve_overlap_deg, 0)}°`,
      "Crank degrees with both valves open around gas-exchange TDC. While both are open the intake and exhaust are connected, so the pressure across them either scavenges the residual out (boosted) or draws it back in (throttled).");
    add("Closed period", `${fmt(r.closed_period_deg, 0)}°`,
      "Crank degrees actually integrated: intake-valve close through to exhaust-valve open.");
  }
  if (r.residual_fraction != null) {
    add("Residual gas", `${fmt(r.residual_fraction * 100, 1)} %`,
      "Burned gas from the last cycle still in the clearance volume when the intake shuts. It is hot, so it warms the charge, and already burned, so it dilutes — this is internal EGR.");
    add("Charge temp at IVC", `${fmt(uconv("temp", r.mixed_temperature_K), 0)} ${ulabel("temp")}`,
      "Fresh charge and hot residual after mixing. This, not the manifold temperature, is where compression starts.");
  }
  if (r.turbine_pressure_ratio != null) {
    add("Turbine expansion", `${fmt(r.turbine_pressure_ratio, 3)}×`,
      "Expansion the turbine needs to drive its compressor, solved from the turbo shaft power balance. The exhaust manifold sits this far above whatever is downstream of it.");
    add("Compressor power", uval("power", r.compressor_power_W, 1),
      "Shaft power the turbo compressor absorbs. A turbo takes it from the exhaust rather than the crank — but pays for it in back-pressure.");
  }
  if (r.exhaust_temperature_K) {
    add("Exhaust temp (EVO)", `${fmt(uconv("temp", r.exhaust_temperature_K), 0)} ${ulabel("temp")}`,
      "Gas temperature when the exhaust valve cracks open. This drives both the turbine's available energy and how much residual is left behind.");
  }
  if (r.peak_burned_temperature_K != null || r.mean_gamma != null) {
    group("Gas model");
  }
  if (r.peak_burned_temperature_K != null) {
    add("Burned zone peak", `${fmt(uconv("temp", r.peak_burned_temperature_K), 0)} ${ulabel("temp")}`,
      "Gas temperature behind the flame front, which runs hotter than the cylinder mean. Frozen composition — real dissociation absorbs energy and would cap this nearer 2800–3000 K, so treat it as an over-estimate.");
    add("End-gas peak", `${fmt(uconv("temp", r.peak_unburned_temperature_K), 0)} ${ulabel("temp")}`,
      "Unburned charge ahead of the flame, compressed but not yet burned. This is the gas that knocks, and it is what the knock margin is now judged on.");
  }
  if (r.mean_gamma != null) {
    add("Mean γ", fmt(r.mean_gamma, 4),
      "Cycle-average ratio of specific heats. Real γ falls from about 1.40 in the cool fresh charge to about 1.25 in hot products, which is why a single fixed value over-predicts peak temperature.");
    add("Gas model", r.two_zone_combustion ? "variable cp · two-zone" : "variable cp · single zone",
      "Specific heats follow temperature and composition, fitted to Cantera. Two-zone tracks burned and unburned gas separately so the end-gas temperature is computed rather than estimated.");
  }
  document.getElementById("configRows").innerHTML = rows.join("");

  const verdicts = [];
  if (L) verdicts.push(`<p><span>Balance</span>${L.balance_verdict}</p>`);
  if (r.breathing_verdict) verdicts.push(`<p><span>Breathing</span>${r.breathing_verdict}</p>`);
  document.getElementById("configVerdicts").innerHTML = verdicts.join("");
}

/** Engineer-mode depth: pro readouts, energy balance, key crank states. */
function renderAnalysis(r) {
  const inp = readInputs();
  const dispL = (Math.PI / 4) * inp.bore_m * inp.bore_m * inp.stroke_m * inp.cylinders * 1000;
  const meanPS = 2 * inp.stroke_m * inp.rpm / 60;
  const cylRate = inp.cylinders * (inp.rpm / 60) * (2 / inp.strokes_per_cycle);
  const airFlow = r.trapped_mass_kg * cylRate * 1000;
  const fuelFlow = r.fuel_mass_per_cycle_kg * cylRate * 1000;
  const specOut = (r.brake_power_W / 1000) / (dispL || 1);
  const tr = r.trace || [];
  let maxdP = 0;
  for (let i = 1; i < tr.length; i++) {
    const dth = tr[i].theta_deg - tr[i - 1].theta_deg;
    if (dth > 0) { const rate = (tr[i].pressure_Pa - tr[i - 1].pressure_Pa) / 1e5 / dth; if (rate > maxdP) maxdP = rate; }
  }
  const rows = [];
  const add = (label, val, tip) => rows.push(`<div class="row"><span class="rk">${label}${tip ? info(tip) : ""}</span><span class="rv">${val}</span></div>`);
  add("Displacement", `${dispL.toFixed(2)} L`);
  add("Mean piston speed", unit === "US" ? `${fmt(meanPS * 3.280839895, 1)} ft/s` : `${fmt(meanPS, 1)} m/s`,
    "Average piston speed — the real limit on revs. Production engines top out near 20–25 m/s.");
  add("Specific output", `${fmt(specOut, 1)} kW/L`, "Power per litre, i.e. how hard it's working. ~50 kW/L NA, 100+ boosted.");
  add("Peak pressure-rise rate", `${fmt(maxdP, 1)} bar/°`, "How violently pressure climbs at combustion — high rates mean combustion noise and knock-like harshness.");
  add("Air flow", `${fmt(airFlow, 1)} g/s`);
  add("Fuel flow", `${fmt(fuelFlow, 2)} g/s`);
  document.getElementById("analysisRows").innerHTML = rows.join("");

  // energy balance: fuel heat released -> indicated work / walls / exhaust
  const heat = r.heat_released_J || 1;
  const work = Math.max(0, r.indicated_work_J);
  const wall = Math.max(0, r.wall_heat_loss_J);
  const exhaust = Math.max(0, heat - work - wall);
  const tot = work + wall + exhaust || 1;
  const segs = [["work", work, "Indicated work", "#e8923e"], ["wall", wall, "Wall heat loss", "#d97757"], ["exhaust", exhaust, "Exhaust", "#4b5468"]];
  document.getElementById("energyBar").innerHTML = segs.map(([c, v]) => `<div class="ebar-seg ${c}" style="flex-grow:${(v / tot).toFixed(4)}"></div>`).join("");
  document.getElementById("energyLegend").innerHTML = segs.map(([c, v, lab, col]) => `<span><i style="background:${col}"></i>${lab} <b>${fmt(v / heat * 100, 0)}%</b></span>`).join("");

  // key crank states from the trace
  const nearest = (th) => tr.reduce((b, t, i) => Math.abs(t.theta_deg - th) < Math.abs(tr[b].theta_deg - th) ? i : b, 0);
  let peakI = 0;
  for (let i = 1; i < tr.length; i++) if (tr[i].pressure_Pa > tr[peakI].pressure_Pa) peakI = i;
  const points = [["BDC (IVC)", -180], ["Ignition", inp.combustion_start_deg], ["Peak", null], ["EVO", 180]];
  const head = document.getElementById("stateHead"), body = document.getElementById("stateBody");
  if (head) head.innerHTML = `<tr><th class="s-name">Point</th><th>θ°</th><th>T ${ulabel("temp")}</th><th>P ${ulabel("press")}</th><th>V ${ulabel("vol")}</th></tr>`;
  if (body) body.innerHTML = points.map(([name, th]) => {
    const idx = th === null ? peakI : nearest(th); const t = tr[idx]; if (!t) return "";
    return `<tr><td class="s-name">${name}</td><td>${fmt(t.theta_deg, 0)}</td><td>${fmt(uconv("temp", t.temperature_K), 0)}</td><td>${fmt(uconv("press", t.pressure_Pa), 1)}</td><td>${fmt(uconv("vol", t.volume_m3), 1)}</td></tr>`;
  }).join("");
}

/** Plain-English description of the engine for Enthusiast mode. */
function renderSummary(r) {
  const el = document.getElementById("summaryText");
  if (!el) return;
  const inp = readInputs();                         // SI values (bore/stroke in m)
  const cyl = inp.cylinders;
  const dispL = (Math.PI / 4) * inp.bore_m * inp.bore_m * inp.stroke_m * cyl * 1000;
  const fuel = inp.fuel;
  const aspWord = inp.aspiration === "turbocharged" ? "turbo" : inp.aspiration === "supercharged" ? "supercharged" : "naturally aspirated";
  const typeWord = fuel === "diesel" ? "diesel" : fuel === "ethanol" ? "ethanol" : fuel === "methanol" ? "methanol" : "petrol";
  const hp = Math.round(r.brake_power_W * 1.34102209e-3);
  const tq = unit === "US" ? `${Math.round(r.brake_torque_Nm * 0.737562149)} lb·ft` : `${Math.round(r.brake_torque_Nm)} N·m`;
  const lam = r.lambda_air;
  const mix = lam > 1.05 ? "lean" : lam < 0.95 ? "rich" : "stoichiometric";
  const cr = inp.compression_ratio;
  let line = `A <b>${dispL.toFixed(1)} L ${aspWord} ${typeWord} ${cyl}-cylinder</b> — about <b>${hp} hp</b> and <b>${tq}</b> at ${Math.round(inp.rpm)} rpm. `;
  line += fuel === "diesel"
    ? `It squeezes the air to <b>${cr.toFixed(0)}:1</b> until it self-ignites the injected fuel — no spark plug — running ${mix} (λ ${fmt(lam, 2)}, as diesels do). `
    : `A spark plug lights a ${mix} mix (λ ${fmt(lam, 2)}) at <b>${cr.toFixed(1)}:1</b> compression. `;
  const warns = r.operating_warnings || [];
  if (warns.some((w) => w.kind === "knock")) line += `⚠ It is <b>knocking</b> — too much compression or boost for this fuel. Back it off or run higher octane.`;
  else if (warns.some((w) => w.kind === "smoke")) line += `⚠ It is over-fuelled into <b>smoke</b> — lean out the fuelling.`;
  else if (warns.some((w) => w.kind === "lean_misfire")) line += `⚠ The mixture is too lean to fire cleanly.`;
  else line += `No knock or smoke flags — a healthy operating point.`;
  el.innerHTML = line;
}

/* ---------- canvas helpers ---------- */
function scaleCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || 600;
  const h = canvas.clientHeight || Number(canvas.getAttribute("height")) || 300;
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(h * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || "#888";

function frame(ctx, x, y, w, h) {
  ctx.strokeStyle = cssVar("--c-grid");
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const yy = y + (h * i) / 4;
    ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x + w, yy); ctx.stroke();
  }
}
function plotLine(ctx, pts, color, width = 1.8, fill = false, baseY = null) {
  if (pts.length < 2) return;
  if (fill && baseY != null) {
    ctx.save(); ctx.globalAlpha = 0.10; ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], baseY);
    pts.forEach(([px, py]) => ctx.lineTo(px, py));
    ctx.lineTo(pts[pts.length - 1][0], baseY);
    ctx.closePath(); ctx.fill(); ctx.restore();
  }
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineJoin = "round";
  ctx.beginPath();
  pts.forEach(([px, py], i) => (i ? ctx.lineTo(px, py) : ctx.moveTo(px, py)));
  ctx.stroke();
}

/* ---------- diagrams ---------- */
const DIAGRAMS = {
  pv: {
    title: "P–V loop", loop: true, color: () => cssVar("--c-pv"),
    x: (t) => uconv("vol", t.volume_m3), y: (t) => uconv("press", t.pressure_Pa),
    xlab: () => `Volume [${ulabel("vol")}]`, ylab: () => `Pressure [${ulabel("press")}]`,
  },
  ts: {
    title: "T–s loop", loop: true, color: () => cssVar("--c-temp"),
    x: (t) => t.entropy_J_per_kg_K, y: (t) => uconv("temp", t.temperature_K),
    xlab: () => "Entropy [J/kg·K]", ylab: () => `Temperature [${ulabel("temp")}]`,
  },
  ptheta: {
    title: "P–θ", loop: false, color: () => cssVar("--c-pv"),
    x: (t) => t.theta_deg, y: (t) => uconv("press", t.pressure_Pa),
    xlab: () => "Crank angle [°]", ylab: () => `Pressure [${ulabel("press")}]`,
  },
  ttheta: {
    title: "T–θ", loop: false, color: () => cssVar("--c-temp"),
    x: (t) => t.theta_deg, y: (t) => uconv("temp", t.temperature_K),
    xlab: () => "Crank angle [°]", ylab: () => `Temperature [${ulabel("temp")}]`,
  },
};

/* Full grid (both axes) with value labels, the way the old console drew it. */
function gridFull(ctx, x, y, w, h, xlo, xhi, ylo, yhi) {
  ctx.strokeStyle = cssVar("--c-grid"); ctx.lineWidth = 1;
  ctx.fillStyle = cssVar("--c-axis"); ctx.font = "500 9px 'JetBrains Mono', monospace";
  const ticks = 4;
  ctx.textAlign = "right"; ctx.textBaseline = "middle";
  for (let i = 0; i <= ticks; i++) {
    const v = ylo + ((yhi - ylo) * i) / ticks;
    const yy = y + h - ((v - ylo) / (yhi - ylo || 1)) * h;
    ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x + w, yy); ctx.stroke();
    ctx.fillText(fmt(v, 0), x - 6, yy);
  }
  ctx.textAlign = "center"; ctx.textBaseline = "top";
  for (let i = 0; i <= ticks; i++) {
    const v = xlo + ((xhi - xlo) * i) / ticks;
    const xx = x + ((v - xlo) / (xhi - xlo || 1)) * w;
    ctx.beginPath(); ctx.moveTo(xx, y); ctx.lineTo(xx, y + h); ctx.stroke();
    ctx.fillText(fmt(v, 0), xx, y + h + 5);
  }
}

/* TDC / BDC markers on a loop, the annotated-node feel of the old diagrams. */
function markNodes(ctx, trace, X, Y, d) {
  const nearest = (target) => trace.reduce((best, t, i) =>
    Math.abs(t.theta_deg - target) < Math.abs(trace[best].theta_deg - target) ? i : best, 0);
  ctx.font = "500 9px 'JetBrains Mono', monospace";
  for (const [idx, label] of [[nearest(0), "TDC"], [nearest(-180), "BDC"]]) {
    const t = trace[idx], x = X(d.x(t)), y = Y(d.y(t));
    ctx.fillStyle = cssVar("--accent"); ctx.beginPath(); ctx.arc(x, y, 3, 0, 7); ctx.fill();
    ctx.fillStyle = cssVar("--c-axis"); ctx.textAlign = "left"; ctx.textBaseline = "bottom";
    ctx.fillText(label, x + 5, y - 3);
  }
}

function drawChart(canvas, kind) {
  if (!canvas || !lastResult || canvas.clientWidth === 0) return;
  const trace = lastResult.trace || [];
  if (trace.length < 2) return;
  const d = DIAGRAMS[kind];
  const { ctx, w, h } = scaleCanvas(canvas);
  ctx.clearRect(0, 0, w, h);
  const padL = 50, padR = 14, padT = 12, padB = 30;
  const px = padL, py = padT, pw = w - padL - padR, ph = h - padT - padB;

  const xs = trace.map(d.x), ys = trace.map(d.y);
  // The ghost shares the axes, so both loops are read at one scale — a ghost on
  // its own axes would make a smaller loop look identical to a bigger one.
  const gxs = ghostTrace ? ghostTrace.map(d.x) : [];
  const gys = ghostTrace ? ghostTrace.map(d.y) : [];
  let xlo = Math.min(...xs, ...gxs), xhi = Math.max(...xs, ...gxs);
  let ylo = Math.min(...ys, ...gys), yhi = Math.max(...ys, ...gys);
  const xp = (xhi - xlo) * 0.05 || 1, yp = (yhi - ylo) * 0.08 || 1;
  xlo -= xp; xhi += xp;
  ylo = d.loop ? ylo - yp : Math.min(ylo, 0); yhi += yp;
  const X = (v) => px + ((v - xlo) / (xhi - xlo || 1)) * pw;
  const Y = (v) => py + ph - ((v - ylo) / (yhi - ylo || 1)) * ph;

  gridFull(ctx, px, py, pw, ph, xlo, xhi, ylo, yhi);

  const pts = xs.map((v, i) => [X(v), Y(ys[i])]);
  const col = d.color();

  // Ghost first, so the live loop always sits on top of it.
  if (ghostTrace) {
    const gpts = gxs.map((v, i) => [X(v), Y(gys[i])]);
    ctx.save();
    ctx.globalAlpha = 0.4;
    ctx.strokeStyle = cssVar("--c-axis");
    ctx.lineWidth = 1.2;
    ctx.lineJoin = "round";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    gpts.forEach(([a, b], i) => (i ? ctx.lineTo(a, b) : ctx.moveTo(a, b)));
    if (d.loop) ctx.closePath();
    ctx.stroke();
    ctx.restore();
  }
  if (d.loop) {
    ctx.save(); ctx.globalAlpha = 0.12; ctx.fillStyle = col;
    ctx.beginPath(); pts.forEach(([a, b], i) => (i ? ctx.lineTo(a, b) : ctx.moveTo(a, b)));
    ctx.closePath(); ctx.fill(); ctx.restore();
  }
  ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.lineJoin = "round";
  ctx.beginPath(); pts.forEach(([a, b], i) => (i ? ctx.lineTo(a, b) : ctx.moveTo(a, b)));
  if (d.loop) ctx.closePath();
  ctx.stroke();

  if (d.loop) markNodes(ctx, trace, X, Y, d);

  // synced position marker driven by the live engine animation
  if (d.loop && markerIdx != null && trace[markerIdx]) {
    const t = trace[markerIdx], mx = X(d.x(t)), my = Y(d.y(t));
    ctx.beginPath(); ctx.arc(mx, my, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff"; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = col; ctx.stroke();
  }

  ctx.fillStyle = cssVar("--c-axis"); ctx.font = "500 9px 'JetBrains Mono', monospace";
  ctx.textAlign = "center"; ctx.textBaseline = "bottom"; ctx.fillText(d.xlab(), px + pw / 2, h - 1);
  ctx.save(); ctx.translate(11, py + ph / 2); ctx.rotate(-Math.PI / 2);
  ctx.textBaseline = "top"; ctx.textAlign = "center"; ctx.fillText(d.ylab(), 0, 0); ctx.restore();
}

function drawAllDiagrams() {
  const pair = diagramMode === "loop" ? ["pv", "ts"] : ["ptheta", "ttheta"];
  const ta = document.getElementById("titleA"), tb = document.getElementById("titleB");
  if (ta) ta.textContent = DIAGRAMS[pair[0]].title;
  if (tb) tb.textContent = DIAGRAMS[pair[1]].title;
  drawChart(document.getElementById("canvasA"), pair[0]);
  drawChart(document.getElementById("canvasB"), pair[1]);
  const note = document.getElementById("diagramNote");
  if (!note) return;
  const base = diagramMode === "loop"
    ? "Two closed loops, live: the P–V area is the indicated work, the T–s area the net heat. Compression and expansion run near-isentropic; combustion sweeps both rightward. Drag any control and watch them respond."
    : "Cylinder pressure and temperature versus crank angle. TDC is 0°; the spike just after TDC is combustion.";
  // An unexplained faint line reads as a rendering bug, so say what it is.
  note.textContent = ghostTrace
    ? `${base} The dashed outline is where you were before this change — both are drawn on the same axes, so the difference is real.`
    : base;
}

/* ---------- living engine animation (the centerpiece) ----------
 * A four-stroke crank-angle clock: animTheta runs 0..720 (0 = TDC of intake,
 * 360 = TDC firing). The piston follows the same slider-crank kinematics as the
 * solver; valves, spark and charge colour follow the cycle; and during the
 * closed strokes (compression + power) the marker tracks the real P–V/T–s loop.
 */
let animTheta = 0;
let animPlaying = true;
let animLast = 0;
let lastLoopDraw = 0;

const inputVal = (key, fallback) => {
  const el = document.querySelector(`[data-key="${key}"]`);
  const v = el ? parseFloat(el.value) : NaN;
  return Number.isNaN(v) ? fallback : v;
};

function strokeName(a) {
  a = ((a % 720) + 720) % 720;
  return a < 180 ? "Intake" : a < 360 ? "Compression" : a < 540 ? "Power" : "Exhaust";
}

/** Trace index for the loop marker, or null during the gas-exchange strokes. */
function engineTraceIndex(a) {
  a = ((a % 720) + 720) % 720;
  const trace = lastResult && lastResult.trace;
  if (!trace || !trace.length || a < 180 || a > 540) return null;
  const tt = a - 360; // crank angle in the trace frame (-180..180)
  let best = 0;
  for (let i = 1; i < trace.length; i++) {
    if (Math.abs(trace[i].theta_deg - tt) < Math.abs(trace[best].theta_deg - tt)) best = i;
  }
  return best;
}

function gasTemperature(a) {
  const intakeT = inputVal("intake_temperature_K", 330);
  const idx = engineTraceIndex(a);
  if (idx != null) return lastResult.trace[idx].temperature_K;
  // gas-exchange strokes: cool fresh charge on intake, hot residual on exhaust
  const aa = ((a % 720) + 720) % 720;
  const endT = lastResult && lastResult.trace.length ? lastResult.trace[lastResult.trace.length - 1].temperature_K : intakeT * 2;
  return aa < 180 ? intakeT : endT;
}

const norm = (v, lo, hi) => Math.max(0, Math.min(1, (v - lo) / Math.max(1, hi - lo)));

/** Zone state at this crank angle, or null when the solve had only one zone. */
function engineZoneState(a) {
  const idx = engineTraceIndex(a);
  if (idx == null || !lastResult || !lastResult.trace) return null;
  const t = lastResult.trace[idx];
  if (!t || t.burned_volume_fraction == null) return null;
  return {
    burnedVolumeFraction: t.burned_volume_fraction,
    unburnedT: t.unburned_temperature_K,
    burnedT: t.burned_temperature_K,
    peakUnburnedT: lastResult.peak_unburned_temperature_K || 1400,
    peakBurnedT: lastResult.peak_burned_temperature_K || 2800,
    knock: (lastResult.operating_warnings || []).some((w) => w.kind === "knock"),
  };
}

/* Draw the chamber as two zones.
 *
 * The flame starts at the plug and grows outward, so the burned region is a
 * disc centred on the plug and clipped to the chamber. Early on it is a true
 * half-disc kernel — area pi r^2 / 2 — which is where the radius comes from;
 * past about 60% burned that under-fills the corners, so the radius eases up to
 * the one that reaches the far corner. The area being matched is the burned
 * *volume* fraction, not the mass fraction: burned gas is several times less
 * dense, so it fills the chamber far faster than it burns.
 */
function drawTwoZoneCharge(ctx, o) {
  const { xL, headY, borePx, chamberH, cx } = o;
  const f = Math.max(0, Math.min(1, o.burnedFraction));

  ctx.save();
  ctx.beginPath();
  ctx.rect(xL, headY, borePx, chamberH);
  ctx.clip();

  // Unburned end-gas fills the chamber first; the burned zone is painted over it.
  const cool = ctx.createLinearGradient(0, headY, 0, headY + chamberH);
  cool.addColorStop(0, o.unburnedTint);
  cool.addColorStop(1, "rgba(20,16,14,0.30)");
  ctx.fillStyle = cool;
  ctx.fillRect(xL, headY, borePx, chamberH);

  if (f > 0.002) {
    const area = borePx * chamberH;
    const rKernel = Math.sqrt((2 * f * area) / Math.PI);
    const rMax = Math.hypot(borePx / 2, chamberH) * 1.02;
    // Ease from the kernel radius to full coverage over the back half of the burn.
    const ease = Math.max(0, Math.min(1, (f - 0.55) / 0.45));
    const r = Math.min(rKernel, rMax) * (1 - ease) + rMax * ease;

    const flame = ctx.createRadialGradient(cx, headY, 0, cx, headY, r);
    flame.addColorStop(0, o.burnedTint);
    flame.addColorStop(0.82, o.burnedTint);
    flame.addColorStop(1, "rgba(255,214,150,0.35)");
    ctx.fillStyle = flame;
    ctx.beginPath();
    ctx.arc(cx, headY, r, 0, Math.PI * 2);
    ctx.fill();

    // The flame boundary itself, only while there is still end-gas to consume.
    if (f < 0.985) {
      ctx.strokeStyle = "rgba(255,236,200,0.55)";
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(cx, headY, r, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  // End-gas about to autoignite: give the far corners a hot edge, which is
  // exactly where knock starts.
  if (o.knock && f > 0.05 && f < 0.98) {
    const glow = ctx.createLinearGradient(xL, 0, xL + borePx, 0);
    glow.addColorStop(0, "rgba(255,138,74,0.42)");
    glow.addColorStop(0.28, "rgba(255,138,74,0)");
    glow.addColorStop(0.72, "rgba(255,138,74,0)");
    glow.addColorStop(1, "rgba(255,138,74,0.42)");
    ctx.fillStyle = glow;
    ctx.fillRect(xL, headY, borePx, chamberH);
  }

  ctx.restore();
}

function gasTint(tnorm) {
  // steel-blue (cool) -> amber -> bright cream (combustion)
  const stops = [[74, 92, 120], [232, 146, 62], [255, 216, 150]];
  let a0, a1, f;
  if (tnorm < 0.6) { a0 = stops[0]; a1 = stops[1]; f = tnorm / 0.6; }
  else { a0 = stops[1]; a1 = stops[2]; f = (tnorm - 0.6) / 0.4; }
  const m = (i) => Math.round(a0[i] + (a1[i] - a0[i]) * Math.max(0, Math.min(1, f)));
  return `rgb(${m(0)},${m(1)},${m(2)})`;
}

function valveLift(a, kind) {
  a = ((a % 720) + 720) % 720;
  const win = kind === "intake" ? [0, 185] : [535, 720];
  if (a < win[0] || a > win[1]) return 0;
  return Math.sin(((a - win[0]) / (win[1] - win[0])) * Math.PI) * 0.9;
}

function drawEngine() {
  const canvas = document.getElementById("engineCanvas");
  if (!canvas || canvas.clientWidth === 0) return;
  const { ctx, w, h } = scaleCanvas(canvas);
  ctx.clearRect(0, 0, w, h);

  const cr = inputVal("compression_ratio", 10.5);
  const bore = inputVal("bore_m", 0.086);
  const stroke = inputVal("stroke_m", 0.086);
  const rodRatio = inputVal("rod_ratio", 3.5);

  // canvas geometry: size the mechanism so the whole thing (cylinder head at
  // TDC down to the bottom of the crank circle) fits centred, then anchor it.
  const pad = 18;
  const cx = w * 0.5;
  const visRod = Math.min(rodRatio, 3.2);            // cap rod for composition
  const headGapFactor = 2 / Math.max(1.4, cr - 1);   // clearance / crank radius
  const crankR = Math.min(60, (h - 2 * pad) / (2 + visRod + 0.45 + headGapFactor));
  const strokePx = 2 * crankR;
  const rodLen = crankR * visRod;
  const pistonH = crankR * 0.9;
  const headGap = crankR * headGapFactor;            // clearance shrinks with CR
  const borePx = Math.max(78, Math.min(w * 0.36, strokePx * (bore / stroke)));
  const cyCrank = pad + (crankR + rodLen) + pistonH * 0.5 + headGap;

  const th = animTheta * Math.PI / 180;
  const dist = crankR * Math.cos(th) + Math.sqrt(rodLen * rodLen - crankR * crankR * Math.sin(th) * Math.sin(th));
  const pinY = cyCrank - dist;                          // piston-pin Y on the axis
  const crownY = pinY - pistonH * 0.5;                  // piston crown
  const crownTDC = (cyCrank - (crankR + rodLen)) - pistonH * 0.5;
  const headY = crownTDC - headGap;                     // combustion-chamber ceiling
  const xL = cx - borePx / 2, xR = cx + borePx / 2;
  const crankPinX = cx + crankR * Math.sin(th);
  const crankPinY = cyCrank - crankR * Math.cos(th);

  // --- cylinder block (gives the bore body) ---
  ctx.fillStyle = "rgba(255,255,255,0.028)";
  roundRect(ctx, xL - 13, headY - 16, borePx + 26, cyCrank - (headY - 16) + 6, 11); ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.07)"; ctx.lineWidth = 1;
  roundRect(ctx, xL - 13, headY - 16, borePx + 26, cyCrank - (headY - 16) + 6, 11); ctx.stroke();

  // --- gas charge ---
  // With a two-zone solve the trace carries the burned volume fraction and both
  // zone temperatures, so the chamber is drawn as what it actually is: a flame
  // kernel growing out from the plug, hot burned gas behind it, cool unburned
  // end-gas pushed to the periphery. Without those the charge falls back to a
  // single bulk tint.
  const Tmin = inputVal("intake_temperature_K", 330);
  const Tmax = (lastResult && lastResult.peak_temperature_K) || 2600;
  const chamberH = Math.max(0, crownY - headY);
  const zone = engineZoneState(animTheta);

  if (zone && chamberH > 1) {
    drawTwoZoneCharge(ctx, {
      xL, xR, headY, borePx, chamberH, cx,
      burnedFraction: zone.burnedVolumeFraction,
      // Normalise each zone against its own peak, or the burned zone saturates
      // to white the instant it lights and the flame loses all its depth.
      unburnedTint: gasTint(0.55 * norm(zone.unburnedT, Tmin, zone.peakUnburnedT)),
      burnedTint: gasTint(0.55 + 0.45 * norm(zone.burnedT, 1400, zone.peakBurnedT)),
      knock: zone.knock,
    });
  } else {
    const tnorm = norm(gasTemperature(animTheta), Tmin, Tmax);
    const tint = gasTint(tnorm);
    const grad = ctx.createLinearGradient(0, headY, 0, crownY);
    grad.addColorStop(0, tint);
    grad.addColorStop(1, `rgba(20,16,14,0.25)`);
    ctx.fillStyle = grad;
    ctx.fillRect(xL, headY, borePx, chamberH);
  }

  // --- cylinder walls: honed-bore look (subtle inner shading + bright liner) ---
  const wallGrad = ctx.createLinearGradient(xL, 0, xR, 0);
  wallGrad.addColorStop(0, "rgba(255,255,255,0.06)"); wallGrad.addColorStop(0.5, "rgba(0,0,0,0)"); wallGrad.addColorStop(1, "rgba(0,0,0,0.10)");
  ctx.fillStyle = wallGrad; ctx.fillRect(xL, headY, borePx, cyCrank - headY);
  ctx.strokeStyle = "rgba(255,255,255,0.20)"; ctx.lineWidth = 2; ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(xL, headY - 6); ctx.lineTo(xL, cyCrank);
  ctx.moveTo(xR, headY - 6); ctx.lineTo(xR, cyCrank);
  ctx.stroke();

  // --- cylinder head (solid block over the bore) ---
  const headGrad = ctx.createLinearGradient(0, headY - 18, 0, headY);
  headGrad.addColorStop(0, "#2b2f37"); headGrad.addColorStop(1, "#1a1d22");
  ctx.fillStyle = headGrad;
  roundRect(ctx, xL - 11, headY - 18, borePx + 22, 16, 6); ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.10)"; ctx.lineWidth = 1;
  roundRect(ctx, xL - 11, headY - 18, borePx + 22, 16, 6); ctx.stroke();

  // --- poppet valves (intake left, exhaust right), seat at the head ---
  // cold intake reads steel, hot exhaust reads terracotta — physical coding, not brand hue
  for (const [kind, vx, tilt, col] of [["intake", cx - borePx * 0.23, -0.16, "#8fa0b5"], ["exhaust", cx + borePx * 0.23, 0.16, "#d97757"]]) {
    const lift = valveLift(animTheta, kind) * 11;
    const sx = Math.sin(tilt), cyv = Math.cos(tilt);
    const seatX = vx + sx * lift, seatY = headY + cyv * lift;
    ctx.strokeStyle = "rgba(176,182,192,0.72)"; ctx.lineWidth = 2.4; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(vx - sx * 26, headY - 25); ctx.lineTo(seatX, seatY); ctx.stroke();
    ctx.lineCap = "butt";
    ctx.save(); ctx.translate(seatX, seatY); ctx.rotate(tilt);
    ctx.fillStyle = lift > 1.2 ? col : "rgba(150,156,166,0.85)";
    ctx.beginPath(); ctx.ellipse(0, 1.5, 8, 3, 0, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }

  // --- ignition: petrol fires a spark plug, diesel injects into hot air ---
  const fuel = (document.querySelector('[data-key="fuel"]') || {}).value || "gasoline";
  const compression = fuel === "diesel";
  const fire = 360 + inputVal("combustion_start_deg", compression ? -8 : -15);
  const da = (((animTheta - fire) % 720) + 720) % 720;

  if (compression) {
    // injector nozzle (thin) at the head centre
    ctx.strokeStyle = "rgba(190,196,206,0.8)"; ctx.lineWidth = 3; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(cx, headY - 21); ctx.lineTo(cx, headY - 1); ctx.stroke();
    ctx.lineCap = "butt";
    // fuel spray cone during injection
    if (da < 38) {
      const sf = 1 - da / 38;
      const reach = Math.min(crownY - headY - 2, (crownY - headY) * (0.4 + 0.5 * (1 - sf)));
      ctx.strokeStyle = `rgba(170,190,230,${0.55 * sf})`; ctx.lineWidth = 1.2;
      for (const ang of [-26, -13, 0, 13, 26]) {
        const a = ang * Math.PI / 180;
        ctx.beginPath(); ctx.moveTo(cx, headY); ctx.lineTo(cx + Math.sin(a) * reach * 0.6, headY + reach); ctx.stroke();
      }
    }
    // compression-ignition bloom: fiery, organic, no electric spark
    const bloom = da < 34 ? Math.sin((da / 34) * Math.PI) : 0;
    if (bloom > 0) {
      const cyb = headY + Math.min(crownY - headY, 16) + 4;
      const r = 8 + bloom * Math.min(borePx * 0.55, 42);
      const g = ctx.createRadialGradient(cx, cyb, 0, cx, cyb, r);
      g.addColorStop(0, `rgba(255,176,96,${0.82 * bloom})`);
      g.addColorStop(0.55, `rgba(232,110,50,${0.35 * bloom})`);
      g.addColorStop(1, "rgba(232,110,50,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cyb, r, 0, Math.PI * 2); ctx.fill();
    }
  } else {
    // spark plug body + electrode
    ctx.strokeStyle = "rgba(190,196,206,0.85)"; ctx.lineWidth = 4.5; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(cx, headY - 22); ctx.lineTo(cx, headY - 6); ctx.stroke();
    ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(cx, headY - 6); ctx.lineTo(cx, headY + 1); ctx.stroke();
    ctx.lineCap = "butt";
    // crisp electric spark (blue-white)
    const spark = da < 24 ? 1 - da / 24 : 0;
    if (spark > 0) {
      const r = 5 + spark * 22;
      const g = ctx.createRadialGradient(cx, headY + 2, 0, cx, headY + 2, r);
      g.addColorStop(0, `rgba(223,233,255,${0.95 * spark})`);
      g.addColorStop(0.5, `rgba(160,190,255,${0.4 * spark})`);
      g.addColorStop(1, "rgba(160,190,255,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, headY + 2, r, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = `rgba(240,246,255,${spark})`; ctx.lineWidth = 1.4;
      ctx.beginPath(); ctx.moveTo(cx, headY + 1); ctx.lineTo(cx - 3, headY + 6); ctx.lineTo(cx + 2, headY + 9); ctx.stroke();
    }
  }

  // ===== rotating assembly (back to front: counterweight, throw, rod, piston, journals) =====
  // counterweight: a shaped bob opposite the crank pin
  const cwAng = th + Math.PI, cwR = crankR * 1.06;
  ctx.fillStyle = "#23262d";
  ctx.beginPath();
  ctx.moveTo(cx, cyCrank);
  ctx.arc(cx, cyCrank, cwR, cwAng - 0.56 * Math.PI, cwAng + 0.56 * Math.PI);
  ctx.closePath(); ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.06)"; ctx.lineWidth = 1; ctx.stroke();
  // crank throw (web) from main journal to crank pin
  ctx.strokeStyle = "#3c414b"; ctx.lineWidth = Math.max(8, crankR * 0.36); ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(cx, cyCrank); ctx.lineTo(crankPinX, crankPinY); ctx.stroke();
  ctx.lineCap = "butt";

  drawRod(ctx, cx, pinY, crankPinX, crankPinY, borePx);
  drawPiston(ctx, cx, xL, xR, crownY, pistonH, pinY, borePx);

  // journals on top
  metalCircle(ctx, crankPinX, crankPinY, Math.max(5, crankR * 0.24), "#565b65", "#2a2d34");
  ctx.fillStyle = cssVar("--accent"); ctx.beginPath(); ctx.arc(crankPinX, crankPinY, Math.max(2, crankR * 0.08), 0, Math.PI * 2); ctx.fill();
  metalCircle(ctx, cx, cyCrank, Math.max(6, crankR * 0.32), "#51565f", "#23262d");
  ctx.fillStyle = "#15171b"; ctx.beginPath(); ctx.arc(cx, cyCrank, Math.max(2, crankR * 0.09), 0, Math.PI * 2); ctx.fill();
}

/* metallic annulus (ring with a dark bore) — rod eyes, pin boss */
function metalRing(ctx, cx, cy, outerR, innerR) {
  const g = ctx.createLinearGradient(cx - outerR, cy - outerR, cx + outerR, cy + outerR);
  g.addColorStop(0, "#565b65"); g.addColorStop(1, "#262931");
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, outerR, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = "#14161a"; ctx.beginPath(); ctx.arc(cx, cy, innerR, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.12)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(cx, cy, outerR, 0, Math.PI * 2); ctx.stroke();
}
function metalCircle(ctx, cx, cy, r, c1, c2) {
  const g = ctx.createLinearGradient(cx - r, cy - r, cx + r, cy + r);
  g.addColorStop(0, c1); g.addColorStop(1, c2);
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.10)"; ctx.lineWidth = 1; ctx.stroke();
}

/* I-beam connecting rod: small end at (x0,y0), big end at (x1,y1) */
function drawRod(ctx, x0, y0, x1, y1, borePx) {
  const ang = Math.atan2(y1 - y0, x1 - x0);
  const nx = Math.cos(ang + Math.PI / 2), ny = Math.sin(ang + Math.PI / 2);
  const smallR = Math.max(5, borePx * 0.095), bigR = Math.max(7, borePx * 0.15);
  const w0 = smallR * 0.5, w1 = bigR * 0.62;
  const grad = ctx.createLinearGradient(x0 - nx * w1, y0 - ny * w1, x0 + nx * w1, y0 + ny * w1);
  grad.addColorStop(0, "#2a2d34"); grad.addColorStop(0.5, "#565b65"); grad.addColorStop(1, "#23262d");
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.moveTo(x0 + nx * w0, y0 + ny * w0);
  ctx.lineTo(x1 + nx * w1, y1 + ny * w1);
  ctx.lineTo(x1 - nx * w1, y1 - ny * w1);
  ctx.lineTo(x0 - nx * w0, y0 - ny * w0);
  ctx.closePath(); ctx.fill();
  ctx.strokeStyle = "rgba(0,0,0,0.30)"; ctx.lineWidth = Math.max(1.5, bigR * 0.2);
  ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();   // I-beam web shadow
  metalRing(ctx, x0, y0, smallR, smallR * 0.48);                          // small end
  metalRing(ctx, x1, y1, bigR, bigR * 0.56);                              // big end
}

/* piston: crown, ring pack with depth, tapered skirt, pin boss */
function drawPiston(ctx, cx, xL, xR, crownY, pistonH, pinY, borePx) {
  const top = crownY, bot = crownY + pistonH;
  const skirt = (xR - xL) * 0.05, ringZone = top + pistonH * 0.44;
  ctx.beginPath();
  ctx.moveTo(xL + 1, top);
  ctx.lineTo(xR - 1, top);
  ctx.lineTo(xR - 1, ringZone);
  ctx.lineTo(xR - 1 - skirt, bot - 3);
  ctx.quadraticCurveTo(xR - 1 - skirt, bot, xR - 5 - skirt, bot);
  ctx.lineTo(xL + 5 + skirt, bot);
  ctx.quadraticCurveTo(xL + 1 + skirt, bot, xL + 1 + skirt, bot - 3);
  ctx.lineTo(xL + 1, ringZone);
  ctx.closePath();
  const pg = ctx.createLinearGradient(xL, 0, xR, 0);
  pg.addColorStop(0, "#191c21"); pg.addColorStop(0.32, "#5a5f69"); pg.addColorStop(0.5, "#3a3f48");
  pg.addColorStop(0.74, "#262931"); pg.addColorStop(1, "#131519");
  ctx.fillStyle = pg; ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.18)"; ctx.lineWidth = 1.4;   // crown highlight
  ctx.beginPath(); ctx.moveTo(xL + 2, top + 0.8); ctx.lineTo(xR - 2, top + 0.8); ctx.stroke();
  for (let i = 0; i < 3; i++) {                                      // ring pack with depth
    const ry = top + pistonH * (0.13 + i * 0.085);
    ctx.strokeStyle = "rgba(0,0,0,0.45)"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(xL + 2, ry); ctx.lineTo(xR - 2, ry); ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,0.09)"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(xL + 2, ry + 1.7); ctx.lineTo(xR - 2, ry + 1.7); ctx.stroke();
  }
  metalRing(ctx, cx, pinY, Math.max(4, borePx * 0.08), Math.max(2, borePx * 0.038));
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function animFrame(ts) {
  if (!animLast) animLast = ts;
  const dt = Math.min(0.05, (ts - animLast) / 1000); animLast = ts;
  if (animPlaying) {
    const cyclesPerSec = 1 / 2.6;            // one full 4-stroke every ~2.6 s
    animTheta = (animTheta + dt * 720 * cyclesPerSec) % 720;
  }
  markerIdx = engineTraceIndex(animTheta);
  drawEngine();
  const label = document.getElementById("strokeLabel");
  if (label) label.textContent = strokeName(animTheta);
  if (ts - lastLoopDraw > 38) { drawAllDiagrams(); lastLoopDraw = ts; } // ~26 fps marker
  requestAnimationFrame(animFrame);
}

/* ---------- dyno sweep ---------- */
const SWEEP_VALUES = {
  rpm: [1000, 1750, 2500, 3250, 4000, 4750, 5500, 6250, 7000],
  compression_ratio: [8, 9, 10, 11, 12, 13, 14, 16, 18],
  equivalence_ratio: [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2],
  intake_pressure_Pa: [1.0e5, 1.3e5, 1.6e5, 1.9e5, 2.2e5, 2.5e5],
  combustion_start_deg: [-35, -28, -21, -14, -7, 0],
};
const SWEEP_LABEL = {
  rpm: "Speed [rpm]", compression_ratio: "Compression ratio",
  equivalence_ratio: "Equivalence ratio φ", intake_pressure_Pa: "Manifold [Pa]",
  combustion_start_deg: "Spark [°CA]",
};
let lastSweep = null;
let ghostSweep = null;   // the sweep before this one, drawn faintly for comparison

async function runSweep() {
  const btn = document.getElementById("runSweep");
  const param = document.getElementById("sweepParameter").value;
  btn.disabled = true; btn.textContent = "…";
  setStatus("Sweeping", "busy");
  try {
    const base = readInputs(); base.include_trace = false;
    const payload = await postJson(API_SWEEP, { base_input: base, sweep_parameter: param, values: SWEEP_VALUES[param] });
    // Keep the outgoing sweep so a re-run draws against it. A sweep is always
    // an explicit button press, so "the previous one" is exactly the right
    // comparison here — unlike the live controls, there is no drag to smear it.
    ghostSweep = lastSweep;
    lastSweep = { payload, param };
    drawDyno();
    const s = payload.summary;
    const compared = ghostSweep && ghostSweep.param === param;
    document.getElementById("dynoNote").textContent =
      `${s.successful_cases} points · peak power ${uval("power", s.peak_brake_power_W, 1)} · peak torque ${uval("torque", s.peak_brake_torque_Nm, 0)}` +
      (s.knock_cases ? ` · ${s.knock_cases} knock-limited` : "") +
      (compared ? " · dashed is your previous sweep" : "");
    setStatus("Solved", "ok");
  } catch (err) {
    setStatus(err.message.slice(0, 48), "err");
  } finally {
    btn.disabled = false; btn.textContent = "Sweep";
  }
}

function drawDyno() {
  const canvas = document.getElementById("dynoCanvas");
  if (!canvas || !lastSweep || canvas.clientWidth === 0) return;
  const { ctx, w, h } = scaleCanvas(canvas);
  ctx.clearRect(0, 0, w, h);
  const cases = (lastSweep.payload.cases || []).filter((c) => c.success && c.output);
  const padL = 46, padR = 46, padT = 22, padB = 28;
  const px = padL, py = padT, pw = w - padL - padR, ph = h - padT - padB;
  frame(ctx, px, py, pw, ph);
  if (cases.length < 2) return;

  const xs = cases.map((c) => c.input_value);
  const power = cases.map((c) => uconv("power", c.output.brake_power_W));
  const torque = cases.map((c) => uconv("torque", c.output.brake_torque_Nm));

  // Only compare like with like: a sweep of a different parameter has a
  // different x axis, so ghosting it would draw a curve that means nothing.
  const gcases = ghostSweep && ghostSweep.param === lastSweep.param
    ? (ghostSweep.payload.cases || []).filter((c) => c.success && c.output)
    : [];
  const gPower = gcases.map((c) => uconv("power", c.output.brake_power_W));
  const gTorque = gcases.map((c) => uconv("torque", c.output.brake_torque_Nm));

  const xlo = Math.min(...xs), xhi = Math.max(...xs), xspan = xhi - xlo || 1;
  // Both runs share the axes, so a curve that moved up really did move up.
  const pHi = Math.max(...power, ...gPower) * 1.08 || 1;
  const tHi = Math.max(...torque, ...gTorque) * 1.08 || 1;
  const X = (v) => px + (pw * (v - xlo)) / xspan;
  const YP = (v) => py + ph - (ph * v) / pHi;
  const YT = (v) => py + ph - (ph * v) / tHi;

  if (gcases.length > 1) {
    const gxs = gcases.map((c) => c.input_value);
    ctx.save();
    ctx.globalAlpha = 0.38;
    ctx.setLineDash([4, 4]);
    plotLine(ctx, gxs.map((v, i) => [X(v), YT(gTorque[i])]), cssVar("--c-torque"), 1.3);
    plotLine(ctx, gxs.map((v, i) => [X(v), YP(gPower[i])]), cssVar("--c-power"), 1.3);
    ctx.restore();
  }

  plotLine(ctx, xs.map((v, i) => [X(v), YT(torque[i])]), cssVar("--c-torque"), 1.9);
  plotLine(ctx, xs.map((v, i) => [X(v), YP(power[i])]), cssVar("--c-power"), 1.9);
  cases.forEach((c, i) => {
    for (const [arr, Yf, col] of [[torque, YT, cssVar("--c-torque")], [power, YP, cssVar("--c-power")]]) {
      ctx.fillStyle = col; ctx.beginPath(); ctx.arc(X(xs[i]), Yf(arr[i]), 2.4, 0, 7); ctx.fill();
    }
  });
  // x ticks
  ctx.fillStyle = cssVar("--c-axis"); ctx.font = "500 9px 'JetBrains Mono', monospace";
  ctx.textAlign = "left"; ctx.textBaseline = "top"; ctx.fillText(fmt(xlo, 0), px, py + ph + 4);
  ctx.textAlign = "right"; ctx.fillText(fmt(xhi, 0), px + pw, py + ph + 4);
  ctx.textAlign = "center"; ctx.fillText(SWEEP_LABEL[lastSweep.param], px + pw / 2, py + ph + 4);
  // legend
  ctx.font = "500 10px 'JetBrains Mono', monospace"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
  ctx.fillStyle = cssVar("--c-power"); ctx.fillRect(px, py - 8, 12, 2);
  ctx.fillStyle = cssVar("--c-axis"); ctx.fillText(`Power [${ulabel("power")}]`, px + 16, py - 7);
  ctx.fillStyle = cssVar("--c-torque"); ctx.fillRect(px + 120, py - 8, 12, 2);
  ctx.fillStyle = cssVar("--c-axis"); ctx.fillText(`Torque [${ulabel("torque")}]`, px + 136, py - 7);
}

/* ---------- boot ---------- */
export function startPiston() {
  buildMetricCards();
  // presets
  const row = document.getElementById("presetRow");
  row.innerHTML = Object.keys(PRESETS).map((n) => `<button class="preset" data-preset="${n}">${n}</button>`).join("");
  row.querySelectorAll(".preset").forEach((b) => b.addEventListener("click", () => {
    armGhost();          // so one preset can be read against the last
    disarmGhost();
    applyPreset(b.dataset.preset);
  }));

  // live inputs. armGhost is registered first so the pre-edit loop is captured
  // before the solve that replaces it.
  document.querySelectorAll("[data-key]").forEach((el) => {
    el.addEventListener("pointerdown", armGhost);
    el.addEventListener("keydown", armGhost);
    el.addEventListener("input", solveDebounced);
    el.addEventListener("change", solveDebounced);
  });
  // A gesture ends on release; the next one is free to capture a fresh ghost.
  document.addEventListener("pointerup", disarmGhost);
  document.addEventListener("keyup", disarmGhost);

  // diagram mode toggle (Loops ⟷ Crank angle)
  document.querySelectorAll("#diagramModeTabs .chart-tab").forEach((t) =>
    t.addEventListener("click", () => {
      diagramMode = t.dataset.mode;
      document.querySelectorAll("#diagramModeTabs .chart-tab").forEach((x) => x.classList.toggle("is-active", x === t));
      drawAllDiagrams();
    }));

  // sweep
  document.getElementById("runSweep").addEventListener("click", runSweep);

  // units
  const unitBtn = document.getElementById("unitToggle");
  unitBtn.addEventListener("click", () => {
    unit = unit === "US" ? "SI" : "US";
    localStorage.setItem(UNIT_KEY, unit);
    unitBtn.textContent = `Units: ${unit}`;
    if (lastResult) renderResult(lastResult);
    if (lastSweep) drawDyno();
  });
  unitBtn.textContent = `Units: ${unit}`;

  // custom engine builder (branching wizard)
  initBuilder();
  const buildBtn = document.getElementById("openBuilder");
  if (buildBtn) buildBtn.addEventListener("click", () => {
    armGhost();          // keep the outgoing engine to read the new build against
    disarmGhost();
    openBuilder(applyBuiltEngine);
  });

  // engine type (petrol / diesel)
  document.querySelectorAll(".etype").forEach((b) =>
    b.addEventListener("click", () => {
      // Picking a stock family clears any bespoke layout/cam/head.
      builderExtras = null;
      const card = document.getElementById("configCard");
      if (card) card.hidden = true;
      applyEngineType(b.dataset.type);
    }));
  // keep type toggle + ignition badge in sync when the fuel itself changes
  const fuelSel = document.getElementById("fuel");
  if (fuelSel) fuelSel.addEventListener("change", syncEngineType);

  // view mode (enthusiast / engineer)
  document.querySelectorAll(".mode-opt").forEach((b) =>
    b.addEventListener("click", () => setMode(b.dataset.mode)));

  // mobile nav menu (hamburger)
  const burger = document.getElementById("navToggle");
  const nav = document.getElementById("missionNav");
  if (burger && nav) {
    const setOpen = (o) => { nav.classList.toggle("open", o); burger.setAttribute("aria-expanded", o ? "true" : "false"); };
    burger.addEventListener("click", (e) => { e.stopPropagation(); setOpen(!nav.classList.contains("open")); });
    nav.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => setOpen(false)));
    document.addEventListener("click", (e) => { if (nav.classList.contains("open") && !nav.contains(e.target) && e.target !== burger) setOpen(false); });
  }

  // living-engine play / pause
  const playBtn = document.getElementById("enginePlay");
  if (playBtn) playBtn.addEventListener("click", () => {
    animPlaying = !animPlaying;
    playBtn.textContent = animPlaying ? "❚❚" : "▶";
    playBtn.setAttribute("aria-label", animPlaying ? "Pause" : "Play");
  });

  // redraw charts on resize
  let rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { drawAllDiagrams(); drawDyno(); }, 150); });

  setMode(localStorage.getItem(MODE_KEY) || "enthusiast");
  syncEngineType();
  updateReadouts();
  solve();
  requestAnimationFrame(animFrame);   // start the live engine
}

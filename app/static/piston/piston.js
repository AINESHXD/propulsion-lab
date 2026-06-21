/* =============================================================
   DAS LABS · PistonLab — console client
   A thin, live client on the Python crank-angle solver
   (POST /piston/simulate, /piston/sweep). The physics is the
   source of truth in app/engine_core/piston; this renders it.
   ============================================================= */

const API_SIM = "/piston/simulate";
const API_SWEEP = "/piston/sweep";

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
  return body;
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

function metricCard(k, valueHtml, primary) {
  return `<div class="metric ${primary ? "primary" : ""}"><div class="k">${k}</div><div class="v">${valueHtml}</div></div>`;
}

function renderResult(r) {
  // metric cards
  document.getElementById("metricCards").innerHTML = [
    metricCard("Brake power", `${fmt(uconv("power", r.brake_power_W), 1)}<span class="u">${ulabel("power")}</span>`, true),
    metricCard("Brake torque", `${fmt(uconv("torque", r.brake_torque_Nm), 0)}<span class="u">${ulabel("torque")}</span>`),
    metricCard("BMEP", `${fmt(uconv("press", r.bmep_Pa), 1)}<span class="u">${ulabel("press")}</span>`),
    metricCard("BSFC", `${fmt(uconv("bsfc", r.bsfc_g_per_kWh), unit === "US" ? 3 : 0)}<span class="u">${ulabel("bsfc")}</span>`),
  ].join("");

  // limit banner
  const banner = document.getElementById("limitBanner");
  banner.innerHTML = (r.operating_warnings || [])
    .map((w) => `<div class="limit ${w.severity}"><span><b>${w.kind.replace("_", " ")}</b> ${w.message}</span></div>`)
    .join("");

  // breakdown ladder
  const rows = [];
  const pr = (label, v, cls = "") => rows.push(`<div class="row ${cls}"><span class="rk">${label}</span><span class="rv">${uval("press", v, 2)}</span></div>`);
  pr("Gross IMEP", r.imep_Pa);
  pr("− Pumping (PMEP)", r.pmep_Pa, "sub");
  pr("Net IMEP", r.net_imep_Pa);
  pr("− Friction (FMEP)", r.fmep_Pa, "sub");
  if (r.supercharger_power_W > 0) {
    rows.push(`<div class="row sub"><span class="rk">− Supercharger drive</span><span class="rv">${uval("power", r.supercharger_power_W, 1)}</span></div>`);
  }
  pr("BMEP", r.bmep_Pa, "total");
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
  drawAllDiagrams();
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
  let xlo = Math.min(...xs), xhi = Math.max(...xs), ylo = Math.min(...ys), yhi = Math.max(...ys);
  const xp = (xhi - xlo) * 0.05 || 1, yp = (yhi - ylo) * 0.08 || 1;
  xlo -= xp; xhi += xp;
  ylo = d.loop ? ylo - yp : Math.min(ylo, 0); yhi += yp;
  const X = (v) => px + ((v - xlo) / (xhi - xlo || 1)) * pw;
  const Y = (v) => py + ph - ((v - ylo) / (yhi - ylo || 1)) * ph;

  gridFull(ctx, px, py, pw, ph, xlo, xhi, ylo, yhi);

  const pts = xs.map((v, i) => [X(v), Y(ys[i])]);
  const col = d.color();
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
  if (note) note.textContent = diagramMode === "loop"
    ? "Two closed loops, live: the P–V area is the indicated work, the T–s area the net heat. Compression and expansion run near-isentropic; combustion sweeps both rightward. Drag any control and watch them respond."
    : "Cylinder pressure and temperature versus crank angle. TDC is 0°; the spike just after TDC is combustion.";
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

  // --- gas charge (temperature-tinted) ---
  const Tmin = inputVal("intake_temperature_K", 330);
  const Tmax = (lastResult && lastResult.peak_temperature_K) || 2600;
  const tnorm = Math.max(0, Math.min(1, (gasTemperature(animTheta) - Tmin) / Math.max(1, Tmax - Tmin)));
  const tint = gasTint(tnorm);
  const grad = ctx.createLinearGradient(0, headY, 0, crownY);
  grad.addColorStop(0, tint);
  grad.addColorStop(1, `rgba(20,16,14,0.25)`);
  ctx.fillStyle = grad;
  ctx.fillRect(xL, headY, borePx, Math.max(0, crownY - headY));

  // --- cylinder walls ---
  ctx.strokeStyle = "rgba(255,255,255,0.16)"; ctx.lineWidth = 2; ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(xL, headY - 8); ctx.lineTo(xL, cyCrank);
  ctx.moveTo(xR, headY - 8); ctx.lineTo(xR, cyCrank);
  ctx.stroke();
  // head
  ctx.strokeStyle = "rgba(255,255,255,0.22)";
  ctx.beginPath(); ctx.moveTo(xL - 10, headY - 8); ctx.lineTo(xR + 10, headY - 8); ctx.stroke();

  // --- valves (intake left, exhaust right), lift downward when open ---
  for (const [kind, vx, col] of [["intake", cx - borePx * 0.24, "#7ba7eb"], ["exhaust", cx + borePx * 0.24, "#d9776a"]]) {
    const lift = valveLift(animTheta, kind) * 12;
    ctx.strokeStyle = "rgba(255,255,255,0.30)"; ctx.lineWidth = 2.4;
    ctx.beginPath(); ctx.moveTo(vx, headY - 22); ctx.lineTo(vx, headY + lift); ctx.stroke();
    ctx.fillStyle = lift > 1 ? col : "rgba(255,255,255,0.30)";
    ctx.beginPath(); ctx.moveTo(vx - 6, headY + lift); ctx.lineTo(vx + 6, headY + lift); ctx.lineTo(vx, headY + lift + 6); ctx.closePath(); ctx.fill();
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

  // --- connecting rod ---
  ctx.strokeStyle = "rgba(210,214,222,0.85)"; ctx.lineWidth = Math.max(4, borePx * 0.07); ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(crankPinX, crankPinY); ctx.lineTo(cx, pinY); ctx.stroke();
  ctx.lineCap = "butt";

  // --- piston ---
  const pg = ctx.createLinearGradient(xL, 0, xR, 0);
  pg.addColorStop(0, "#23262d"); pg.addColorStop(0.5, "#3c414b"); pg.addColorStop(1, "#23262d");
  ctx.fillStyle = pg;
  roundRect(ctx, xL + 2, crownY, borePx - 4, pistonH, 4); ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.10)"; ctx.lineWidth = 1;
  for (let i = 1; i <= 3; i++) { const ry = crownY + 5 + i * 4; ctx.beginPath(); ctx.moveTo(xL + 4, ry); ctx.lineTo(xR - 4, ry); ctx.stroke(); }
  ctx.fillStyle = "rgba(180,186,196,0.9)"; ctx.beginPath(); ctx.arc(cx, pinY, Math.max(3, borePx * 0.05), 0, Math.PI * 2); ctx.fill();

  // --- crankshaft ---
  ctx.strokeStyle = "rgba(255,255,255,0.10)"; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.arc(cx, cyCrank, crankR, 0, Math.PI * 2); ctx.stroke();
  // counterweight opposite the pin
  ctx.fillStyle = "rgba(60,65,75,0.9)";
  ctx.beginPath(); ctx.arc(cx - crankR * Math.sin(th), cyCrank + crankR * Math.cos(th), crankR * 0.7, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = "rgba(210,214,222,0.85)"; ctx.lineWidth = Math.max(3, borePx * 0.05);
  ctx.beginPath(); ctx.moveTo(cx, cyCrank); ctx.lineTo(crankPinX, crankPinY); ctx.stroke();
  ctx.fillStyle = cssVar("--accent"); ctx.beginPath(); ctx.arc(crankPinX, crankPinY, Math.max(3, borePx * 0.045), 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = "#9aa0aa"; ctx.beginPath(); ctx.arc(cx, cyCrank, 3, 0, Math.PI * 2); ctx.fill();
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

async function runSweep() {
  const btn = document.getElementById("runSweep");
  const param = document.getElementById("sweepParameter").value;
  btn.disabled = true; btn.textContent = "…";
  setStatus("Sweeping", "busy");
  try {
    const base = readInputs(); base.include_trace = false;
    const payload = await postJson(API_SWEEP, { base_input: base, sweep_parameter: param, values: SWEEP_VALUES[param] });
    lastSweep = { payload, param };
    drawDyno();
    const s = payload.summary;
    document.getElementById("dynoNote").textContent =
      `${s.successful_cases} points · peak power ${uval("power", s.peak_brake_power_W, 1)} · peak torque ${uval("torque", s.peak_brake_torque_Nm, 0)}` +
      (s.knock_cases ? ` · ${s.knock_cases} knock-limited` : "");
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
  const xlo = Math.min(...xs), xhi = Math.max(...xs), xspan = xhi - xlo || 1;
  const pHi = Math.max(...power) * 1.08 || 1, tHi = Math.max(...torque) * 1.08 || 1;
  const X = (v) => px + (pw * (v - xlo)) / xspan;
  const YP = (v) => py + ph - (ph * v) / pHi;
  const YT = (v) => py + ph - (ph * v) / tHi;
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
  // presets
  const row = document.getElementById("presetRow");
  row.innerHTML = Object.keys(PRESETS).map((n) => `<button class="preset" data-preset="${n}">${n}</button>`).join("");
  row.querySelectorAll(".preset").forEach((b) => b.addEventListener("click", () => applyPreset(b.dataset.preset)));

  // live inputs
  document.querySelectorAll("[data-key]").forEach((el) => {
    el.addEventListener("input", solveDebounced);
    el.addEventListener("change", solveDebounced);
  });

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

  // engine type (petrol / diesel)
  document.querySelectorAll(".etype").forEach((b) =>
    b.addEventListener("click", () => applyEngineType(b.dataset.type)));
  // keep type toggle + ignition badge in sync when the fuel itself changes
  const fuelSel = document.getElementById("fuel");
  if (fuelSel) fuelSel.addEventListener("change", syncEngineType);

  // view mode (enthusiast / engineer)
  document.querySelectorAll(".mode-opt").forEach((b) =>
    b.addEventListener("click", () => setMode(b.dataset.mode)));

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

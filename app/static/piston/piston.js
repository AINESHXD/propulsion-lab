/* PistonLab — air-standard reciprocating-engine cycle simulator.
 *
 * Pure client-side physics. Models the three classic air-standard cycles used to
 * teach reciprocating internal-combustion engines:
 *
 *   Otto   — spark ignition, heat added at constant volume.
 *   Diesel — compression ignition, heat added at constant pressure.
 *   Dual   — a split: some heat at constant volume, the rest at constant pressure
 *            (a closer idealisation of a real high-speed diesel).
 *
 * Assumptions are the standard "cold-air-standard" set, and we say so on the page:
 *   - the working fluid is a fixed mass of air behaving as an ideal gas,
 *   - constant specific heats (no temperature dependence, no real combustion
 *     products), so gamma is a constant you pick,
 *   - compression and expansion are reversible and adiabatic (isentropic),
 *   - heat addition replaces combustion; heat rejection replaces the exhaust/intake
 *     blowdown as an equivalent constant-volume process.
 *
 * The numbers are therefore *indicated, ideal* values. A real engine of the same
 * geometry makes less power: friction, pumping work, heat loss, finite burn rate
 * and incomplete combustion all subtract. The page labels them that way.
 */

const R_AIR = 287.0; // J/(kg·K), specific gas constant for dry air

// ---------------------------------------------------------------------------
// Cycle solver
// ---------------------------------------------------------------------------

/**
 * Solve an air-standard cycle.
 *
 * @param {object} o
 * @param {"otto"|"diesel"|"dual"} o.cycle
 * @param {number} o.r       compression ratio V1/V2 (-)
 * @param {number} o.T1      intake temperature (K)
 * @param {number} o.P1      intake pressure (Pa)
 * @param {number} o.qin     specific heat added per cycle (J/kg)
 * @param {number} o.gamma   ratio of specific heats (-)
 * @param {number} [o.dualFraction] for the dual cycle, fraction of qin added at
 *                                   constant volume (0..1); ignored otherwise
 * @returns {object} states[] + performance
 */
export function solveCycle(o) {
  const { cycle, r, T1, P1, qin, gamma } = o;
  const dualFraction = o.dualFraction ?? 0.5;

  const cv = R_AIR / (gamma - 1);
  const cp = gamma * cv;

  // State 1 — bottom of the intake stroke (cylinder full).
  const v1 = (R_AIR * T1) / P1; // specific volume, m³/kg
  const s1 = 0; // reference entropy; we plot s - s1

  // 1 -> 2  isentropic compression to v2 = v1 / r.
  const v2 = v1 / r;
  const T2 = T1 * Math.pow(r, gamma - 1);
  const P2 = P1 * Math.pow(r, gamma);

  const states = [
    { name: "1", T: T1, P: P1, v: v1 },
    { name: "2", T: T2, P: P2, v: v2 },
  ];

  // Heat-addition stage(s). Each cycle differs only here.
  let qCv = 0; // heat added at constant volume
  let qCp = 0; // heat added at constant pressure
  if (cycle === "otto") {
    qCv = qin;
  } else if (cycle === "diesel") {
    qCp = qin;
  } else {
    qCv = dualFraction * qin;
    qCp = qin - qCv;
  }

  // Constant-volume heat addition 2 -> 3a (skipped for pure Diesel).
  const Ta = T2 + qCv / cv;
  const Pa = P2 * (Ta / T2);
  const va = v2;
  if (qCv > 0) states.push({ name: states.length + 1 + "", T: Ta, P: Pa, v: va });

  // Constant-pressure heat addition 3a -> 3b (skipped for pure Otto).
  const Tb = Ta + qCp / cp;
  const Pb = Pa; // constant pressure
  const vb = va * (Tb / Ta);
  if (qCp > 0) states.push({ name: states.length + 1 + "", T: Tb, P: Pb, v: vb });

  // Peak state is wherever combustion ends.
  const Tpeak = Tb;
  const Ppeak = qCp > 0 ? Pb : Pa;
  const vpeak = qCp > 0 ? vb : va;

  // Expansion stage back to the full cylinder volume v1 (isentropic).
  const vExpStart = vpeak;
  const Texp = Tpeak;
  const Pexp = Ppeak;
  const v4 = v1;
  const T4 = Texp * Math.pow(vExpStart / v4, gamma - 1);
  const P4 = Pexp * Math.pow(vExpStart / v4, gamma);
  states.push({ name: states.length + 1 + "", T: T4, P: P4, v: v4 });

  // 4 -> 1 constant-volume heat rejection closes the loop.
  const qout = cv * (T4 - T1);

  const wNet = qin - qout; // J/kg, first law on the closed cycle
  const efficiency = wNet / qin;

  // Mean effective pressure: net work spread over the swept (displaced) volume.
  const mep = wNet / (v1 - v2); // Pa

  const cutoffRatio = qCp > 0 ? vb / va : 1; // Diesel/Dual cutoff
  const pressureRatio = qCv > 0 ? Pa / P2 : 1; // Dual constant-volume pressure jump

  // Attach entropy (relative to state 1) to every state for the T-s plot.
  for (const st of states) {
    st.s = cp * Math.log(st.T / T1) - R_AIR * Math.log(st.P / P1);
  }

  return {
    cycle,
    gamma,
    cv,
    cp,
    states,
    qin,
    qout,
    wNet,
    efficiency,
    mep,
    Tpeak,
    Ppeak,
    cutoffRatio,
    pressureRatio,
    v1,
    v2,
  };
}

/**
 * Closed-form thermal efficiency for each cycle — used to cross-check the
 * first-law result from solveCycle (they must agree).
 */
export function closedFormEfficiency(o) {
  const { cycle, r, gamma } = o;
  const base = 1 - 1 / Math.pow(r, gamma - 1);
  if (cycle === "otto") return base;

  // Diesel needs the cutoff ratio; Dual needs cutoff + pressure ratio. We take
  // them from a solved cycle so the heat split is consistent.
  const sol = solveCycle(o);
  const rc = sol.cutoffRatio;
  const rp = sol.pressureRatio;
  if (cycle === "diesel") {
    return 1 - (1 / Math.pow(r, gamma - 1)) * ((Math.pow(rc, gamma) - 1) / (gamma * (rc - 1)));
  }
  // Dual.
  const num = rp * Math.pow(rc, gamma) - 1;
  const den = (rp - 1) + gamma * rp * (rc - 1);
  return 1 - (1 / Math.pow(r, gamma - 1)) * (num / den);
}

/**
 * Translate ideal specific work into real-world geometry numbers: displacement,
 * trapped air mass, indicated power and torque. Still *indicated* (no friction).
 */
export function enginePerformance(sol, geom) {
  const { boreMm, strokeMm, cylinders, rpm, strokesPerCycle } = geom;
  const bore = boreMm / 1000;
  const stroke = strokeMm / 1000;

  const sweptPerCyl = (Math.PI / 4) * bore * bore * stroke; // m³
  const sweptTotal = sweptPerCyl * cylinders;
  const r = sol.v1 / sol.v2;
  const clearanceTotal = sweptTotal / (r - 1);
  const v1Total = sweptTotal + clearanceTotal; // total cylinder volume at BDC

  // Trapped air mass (all cylinders) from the intake state.
  const P1 = (sol.states[0].P);
  const T1 = (sol.states[0].T);
  const massPerCycle = (P1 * v1Total) / (R_AIR * T1);

  const workPerCycle = sol.wNet * massPerCycle; // J, all cylinders, one cycle each
  // Power cycles per second: a 4-stroke fires once every two revolutions.
  const cyclesPerSec = (rpm / 60) * (2 / strokesPerCycle);
  const powerW = workPerCycle * cyclesPerSec;
  const torqueNm = powerW / (2 * Math.PI * (rpm / 60));

  return {
    sweptTotalL: sweptTotal * 1000, // litres
    sweptPerCylCc: sweptPerCyl * 1e6, // cc
    massPerCycleMg: massPerCycle * 1e6, // mg
    workPerCycleJ: workPerCycle,
    indicatedPowerKW: powerW / 1000,
    indicatedPowerHP: powerW / 745.7,
    indicatedTorqueNm: torqueNm,
  };
}

// ---------------------------------------------------------------------------
// Process-curve sampling for the diagrams
// ---------------------------------------------------------------------------

/** Sample an isentropic P-v process between two states. */
function isentropicPath(a, b, gamma, n = 40) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const v = a.v + ((b.v - a.v) * i) / n;
    const P = a.P * Math.pow(a.v / v, gamma);
    pts.push({ v, P, T: (P * v) / R_AIR });
  }
  return pts;
}

/** Build the full closed P-v polyline for the cycle (BDC..compress..burn..expand..reject). */
export function pvLoop(sol) {
  const s = sol.states;
  const g = sol.gamma;
  let pts = [];
  // 1 -> 2 isentropic compression
  pts = pts.concat(isentropicPath(s[0], s[1], g));
  // middle: walk the heat-addition states with straight segments (const-V is
  // vertical in P-v, const-P is horizontal — both are straight lines).
  for (let i = 1; i < s.length - 2; i++) {
    pts.push({ v: s[i].v, P: s[i].P });
    pts.push({ v: s[i + 1].v, P: s[i + 1].P });
  }
  const last = s.length - 1;
  // expansion (penultimate -> last) isentropic
  pts = pts.concat(isentropicPath(s[last - 1], s[last], g));
  // 4 -> 1 constant-volume rejection (vertical line back to start)
  pts.push({ v: s[last].v, P: s[last].P });
  pts.push({ v: s[0].v, P: s[0].P });
  return pts;
}

/** Build the closed T-s polyline. Isentropes are vertical; heat processes curve. */
export function tsLoop(sol) {
  const s = sol.states;
  const cp = sol.cp;
  const cv = sol.cv;
  const T1 = s[0].T;
  const P1 = s[0].P;
  const entropyOf = (T, P) => cp * Math.log(T / T1) - R_AIR * Math.log(P / P1);

  const pts = [];
  // 1 -> 2 isentropic (vertical, s const)
  pts.push({ s: s[0].s, T: s[0].T });
  pts.push({ s: s[1].s, T: s[1].T });
  // heat-addition states: sample smoothly between successive states using
  // the relevant process (const-V: s = s_i + cv ln(T/Ti); const-P: cp ln).
  for (let i = 1; i < s.length - 2; i++) {
    const a = s[i];
    const b = s[i + 1];
    const constV = Math.abs(a.v - b.v) < 1e-9;
    const n = 30;
    for (let k = 1; k <= n; k++) {
      const T = a.T + ((b.T - a.T) * k) / n;
      const P = constV ? a.P * (T / a.T) : a.P; // const-V: P∝T; const-P: P fixed
      pts.push({ s: entropyOf(T, P), T });
    }
  }
  const last = s.length - 1;
  // expansion isentropic (vertical)
  pts.push({ s: s[last - 1].s, T: s[last - 1].T });
  pts.push({ s: s[last].s, T: s[last].T });
  // 4 -> 1 constant-volume rejection: P ∝ T
  const a = s[last];
  const n = 30;
  for (let k = 1; k <= n; k++) {
    const T = a.T + ((T1 - a.T) * k) / n;
    const P = a.P * (T / a.T);
    pts.push({ s: entropyOf(T, P), T });
  }
  return pts;
}

// ---------------------------------------------------------------------------
// Canvas plotting (no chart library; just 2D context)
// ---------------------------------------------------------------------------

function setupCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.round(rect.width * dpr));
  canvas.height = Math.max(1, Math.round(rect.height * dpr));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w: rect.width, h: rect.height };
}

const COL = {
  grid: "rgba(255,255,255,0.06)",
  axis: "rgba(255,255,255,0.28)",
  text: "#8b9099",
  line: "#f0883e",
  fill: "rgba(240,136,62,0.10)",
  node: "#fff",
};

function drawPlot(canvas, pts, nodes, opts) {
  const { ctx, w, h } = setupCanvas(canvas);
  ctx.clearRect(0, 0, w, h);
  const padL = 52, padR = 16, padT = 18, padB = 38;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;

  const xs = pts.map((p) => p[opts.xKey]);
  const ys = pts.map((p) => p[opts.yKey]);
  let xMin = Math.min(...xs), xMax = Math.max(...xs);
  let yMin = Math.min(...ys), yMax = Math.max(...ys);
  // pad ranges a touch
  const xPad = (xMax - xMin) * 0.06 || 1;
  const yPad = (yMax - yMin) * 0.08 || 1;
  xMin -= xPad; xMax += xPad;
  yMin = opts.yFromZero ? 0 : yMin - yPad;
  yMax += yPad;

  const X = (v) => padL + ((v - xMin) / (xMax - xMin)) * plotW;
  const Y = (v) => padT + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

  // gridlines
  ctx.strokeStyle = COL.grid;
  ctx.fillStyle = COL.text;
  ctx.lineWidth = 1;
  ctx.font = "10px ui-monospace, monospace";
  const ticks = 5;
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let i = 0; i <= ticks; i++) {
    const v = yMin + ((yMax - yMin) * i) / ticks;
    const y = Y(v);
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
    ctx.fillText(opts.fmtY(v), padL - 7, y);
  }
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (let i = 0; i <= ticks; i++) {
    const v = xMin + ((xMax - xMin) * i) / ticks;
    const x = X(v);
    ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, h - padB); ctx.stroke();
    ctx.fillText(opts.fmtX(v), x, h - padB + 6);
  }

  // axis titles
  ctx.fillStyle = COL.text;
  ctx.font = "11px -apple-system, system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(opts.xLabel, padL + plotW / 2, h - 14);
  ctx.save();
  ctx.translate(13, padT + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(opts.yLabel, 0, 0);
  ctx.restore();

  // filled loop
  ctx.beginPath();
  pts.forEach((p, i) => {
    const x = X(p[opts.xKey]); const y = Y(p[opts.yKey]);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.closePath();
  ctx.fillStyle = COL.fill;
  ctx.fill();
  ctx.strokeStyle = COL.line;
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.stroke();

  // state nodes + labels
  if (nodes) {
    ctx.fillStyle = COL.node;
    ctx.strokeStyle = "rgba(0,0,0,0.6)";
    ctx.font = "10px ui-monospace, monospace";
    for (const nd of nodes) {
      const x = X(nd[opts.xKey]); const y = Y(nd[opts.yKey]);
      ctx.beginPath(); ctx.arc(x, y, 3.4, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#cfd3da";
      ctx.textAlign = "left";
      ctx.textBaseline = "bottom";
      ctx.fillText(nd.name, x + 5, y - 3);
      ctx.fillStyle = COL.node;
    }
  }
}

// ---------------------------------------------------------------------------
// UI wiring
// ---------------------------------------------------------------------------

const $ = (id) => document.getElementById(id);
const fmt = (x, d = 2) => (Number.isFinite(x) ? x.toFixed(d) : "—");

function readInputs() {
  return {
    cycle: $("cycle").value,
    r: parseFloat($("r").value),
    T1: parseFloat($("T1").value),
    P1: parseFloat($("P1").value) * 1000, // kPa -> Pa
    qin: parseFloat($("qin").value) * 1000, // kJ/kg -> J/kg
    gamma: parseFloat($("gamma").value),
    dualFraction: parseFloat($("dualFraction").value),
  };
}

function readGeometry() {
  return {
    boreMm: parseFloat($("bore").value),
    strokeMm: parseFloat($("stroke").value),
    cylinders: parseInt($("cylinders").value, 10),
    rpm: parseFloat($("rpm").value),
    strokesPerCycle: parseInt($("strokes").value, 10),
  };
}

function refresh() {
  const inp = readInputs();
  // guard rails
  if (!(inp.r > 1) || !(inp.gamma > 1) || !(inp.qin > 0)) return;

  const sol = solveCycle(inp);
  const perf = enginePerformance(sol, readGeometry());

  // headline metrics
  $("mEff").textContent = (sol.efficiency * 100).toFixed(1) + "%";
  $("mWork").textContent = (sol.wNet / 1000).toFixed(0);
  $("mMep").textContent = (sol.mep / 1000).toFixed(0);
  $("mPower").textContent = perf.indicatedPowerKW.toFixed(1);

  // secondary readouts
  $("rPeakT").textContent = fmt(sol.Tpeak, 0) + " K";
  $("rPeakP").textContent = fmt(sol.Ppeak / 1e5, 1) + " bar";
  $("rQout").textContent = fmt(sol.qout / 1000, 0) + " kJ/kg";
  $("rCutoff").textContent = fmt(sol.cutoffRatio, 3);
  $("rDisp").textContent = fmt(perf.sweptTotalL, 2) + " L";
  $("rTorque").textContent = fmt(perf.indicatedTorqueNm, 0) + " N·m";
  $("rHp").textContent = fmt(perf.indicatedPowerHP, 0) + " ihp";
  $("rMass").textContent = fmt(perf.massPerCycleMg, 1) + " mg";

  // state table
  const tbody = $("stateBody");
  tbody.innerHTML = "";
  sol.states.forEach((st) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${st.name}</td>` +
      `<td>${(st.P / 1e5).toFixed(2)}</td>` +
      `<td>${st.T.toFixed(0)}</td>` +
      `<td>${st.v.toFixed(4)}</td>`;
    tbody.appendChild(tr);
  });

  // diagrams
  const pv = pvLoop(sol);
  drawPlot($("pvCanvas"), pv, sol.states, {
    xKey: "v", yKey: "P", yFromZero: true,
    xLabel: "specific volume  v  (m³/kg)",
    yLabel: "pressure  P  (bar)",
    fmtX: (x) => x.toFixed(2),
    fmtY: (y) => (y / 1e5).toFixed(0),
  });
  // T-s wants pressure-derived entropy; convert P axis to bar visually only for PV.
  const ts = tsLoop(sol);
  drawPlot($("tsCanvas"), ts, sol.states.map((s) => ({ name: s.name, s: s.s, T: s.T })), {
    xKey: "s", yKey: "T", yFromZero: true,
    xLabel: "entropy  s − s₁  (J/kg·K)",
    yLabel: "temperature  T  (K)",
    fmtX: (x) => x.toFixed(0),
    fmtY: (y) => y.toFixed(0),
  });
}

function applyCycleVisibility() {
  const cycle = $("cycle").value;
  // The dual split slider only matters for the dual cycle.
  $("dualRow").style.display = cycle === "dual" ? "" : "none";
  const blurb = {
    otto: "Spark ignition. Heat added at constant volume — the petrol-engine idealisation.",
    diesel: "Compression ignition. Heat added at constant pressure as fuel sprays in.",
    dual: "Limited-pressure cycle. Part of the heat at constant volume, the rest at constant pressure — closest to a real high-speed diesel.",
  }[cycle];
  $("cycleBlurb").textContent = blurb;
}

const PRESETS = {
  petrol: { cycle: "otto", r: 10, T1: 300, P1: 100, qin: 1800, gamma: 1.4, dualFraction: 0.5, bore: 86, stroke: 86, cylinders: 4, rpm: 6000, strokes: 4 },
  turbo: { cycle: "otto", r: 9.5, T1: 320, P1: 160, qin: 2000, gamma: 1.38, dualFraction: 0.5, bore: 82.5, stroke: 92.8, cylinders: 4, rpm: 5500, strokes: 4 },
  diesel: { cycle: "diesel", r: 18, T1: 310, P1: 120, qin: 1500, gamma: 1.37, dualFraction: 0.5, bore: 84, stroke: 90, cylinders: 4, rpm: 4000, strokes: 4 },
  truck: { cycle: "dual", r: 17, T1: 320, P1: 200, qin: 1700, gamma: 1.35, dualFraction: 0.45, bore: 130, stroke: 150, cylinders: 6, rpm: 1800, strokes: 4 },
};

function applyPreset(name) {
  const p = PRESETS[name];
  if (!p) return;
  $("cycle").value = p.cycle;
  $("r").value = p.r;
  $("T1").value = p.T1;
  $("P1").value = p.P1;
  $("qin").value = p.qin;
  $("gamma").value = p.gamma;
  $("dualFraction").value = p.dualFraction;
  $("bore").value = p.bore;
  $("stroke").value = p.stroke;
  $("cylinders").value = p.cylinders;
  $("rpm").value = p.rpm;
  $("strokes").value = p.strokes;
  syncRangeLabels();
  applyCycleVisibility();
  refresh();
}

function syncRangeLabels() {
  document.querySelectorAll("input[type=range]").forEach((el) => {
    const out = document.querySelector(`[data-for="${el.id}"]`);
    if (out) out.textContent = el.value;
  });
}

export function startPiston() {
  // wire every control to a live refresh
  document.querySelectorAll(".control input, .control select").forEach((el) => {
    el.addEventListener("input", () => {
      syncRangeLabels();
      if (el.id === "cycle") applyCycleVisibility();
      refresh();
    });
  });
  document.querySelectorAll("[data-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-preset]").forEach((b) => b.classList.remove("on"));
      btn.classList.add("on");
      applyPreset(btn.dataset.preset);
    });
  });
  window.addEventListener("resize", () => refresh());

  applyCycleVisibility();
  syncRangeLabels();
  applyPreset("petrol");
  document.querySelector('[data-preset="petrol"]').classList.add("on");
}

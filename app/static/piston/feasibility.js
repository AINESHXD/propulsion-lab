/* =========================================================
   DAS LABS · PistonLab: feasibility report
   ---------------------------------------------------------
   Renders POST /piston/feasibility. Every number here comes from the server,
   which gets it from the solver; this file only lays it out and draws it.
   Charts are plain canvas, redrawn on resize, in the console's own colours.
   ========================================================= */

const API = "/piston/feasibility";
let lastReport = null;

const css = (n, f = "#888") => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || f;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const n = (v, d = 1) => (v == null || !Number.isFinite(Number(v)) ? "n/a"
  : Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }));
const sig = (v) => (v == null ? "n/a" : Math.abs(v) >= 100 ? n(v, 0) : Math.abs(v) >= 10 ? n(v, 1) : n(v, 2));
const unit = (u) => (u ? ` ${u}` : "");
const STATUS_WORD = { pass: "Pass", caution: "Caution", fail: "Fail", "n/a": "Not assessed" };
const VERDICT_WORD = { feasible: "Feasible", marginal: "Marginal", not_feasible: "Not feasible" };

function lever(v, lev) {
  if (v == null) return "n/a";
  if (lev === "intake_pressure_Pa") return `${n(v / 1e5, 2)} bar`;
  if (lev === "rpm") return `${n(v, 0)} rpm`;
  if (lev === "compression_ratio") return `${n(v, 1)}:1`;
  if (lev === "burn_duration_deg") return `${n(v, 0)}°`;
  return n(v, 2);
}

/* ---------- canvas plumbing ---------- */
function canvasCtx(canvas, height) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = canvas.clientWidth || 600;
  canvas.style.height = `${height}px`;
  canvas.width = Math.round(w * dpr); canvas.height = Math.round(height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, height);
  ctx.font = `11px ${css("--font-mono", "monospace")}`;
  return { ctx, w, h: height };
}
function ticks(lo, hi, count = 5) {
  const span = hi - lo || 1;
  const raw = span / count, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) || 10 * mag;
  const out = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(+t.toFixed(10));
  return out;
}

/* Where a value sits against its own limits, on one common scale: the caution
   threshold lands at 0.75 and the limit at 1.0 for every criterion, linearly
   in the criterion's own units. Works for "max" and "min" checks alike. */
function position(c) {
  if (c.value == null || c.caution == null || c.limit == null || c.kind === "flag") return null;
  const span = c.limit - c.caution;
  if (!span) return null;
  return Math.max(0, Math.min(1.6, 0.75 + 0.25 * (c.value - c.caution) / span));
}

function drawEnvelope(canvas, before, after) {
  const rows = before.filter((c) => position(c) != null);
  // On a narrow screen the label gets its own line above the bar, or the two
  // collide; on a wide one they sit side by side.
  const stacked = (canvas.clientWidth || 600) < 560;
  const rowH = stacked ? 40 : 30, top = 18, labelW = stacked ? 0 : Math.min(230, canvas.clientWidth * 0.42);
  const { ctx, w, h } = canvasCtx(canvas, top + rows.length * rowH + 26);
  // the right gutter fits the widest printed value, so none is clipped
  const gutter = 12 + Math.max(...rows.map((c) => ctx.measureText(`${sig(c.value)}${unit(c.unit)}`).width), 40);
  const x0 = stacked ? 0 : labelW + 8, x1 = w - gutter, X = (p) => x0 + (p / 1.6) * (x1 - x0);
  const barY = stacked ? 14 : 3;
  const col = { pass: css("--ok"), caution: css("--warn"), fail: css("--err") };

  // infeasible zone, caution band, and the two reference lines
  ctx.fillStyle = "rgba(217,118,112,0.07)"; ctx.fillRect(X(1), top - 6, X(1.6) - X(1), rows.length * rowH + 4);
  ctx.fillStyle = "rgba(212,161,85,0.06)"; ctx.fillRect(X(0.75), top - 6, X(1) - X(0.75), rows.length * rowH + 4);
  ctx.setLineDash([3, 3]); ctx.strokeStyle = css("--warn"); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(X(0.75), top - 8); ctx.lineTo(X(0.75), top + rows.length * rowH); ctx.stroke();
  ctx.setLineDash([]); ctx.strokeStyle = css("--err");
  ctx.beginPath(); ctx.moveTo(X(1), top - 8); ctx.lineTo(X(1), top + rows.length * rowH); ctx.stroke();
  // labels sit either side of their lines so they never run together
  ctx.fillStyle = css("--warn"); ctx.textAlign = "right"; ctx.fillText("caution", X(0.75) - 4, h - 8);
  ctx.fillStyle = css("--err"); ctx.textAlign = "left"; ctx.fillText("limit", X(1) + 4, h - 8);

  const afterBy = Object.fromEntries((after || []).map((c) => [c.key, c]));
  rows.forEach((c, i) => {
    const y = top + i * rowH;
    ctx.textAlign = "left"; ctx.fillStyle = css("--text-2");
    const maxChars = stacked ? 48 : 30;
    ctx.fillText(c.label.length > maxChars ? c.label.slice(0, maxChars - 1) + "…" : c.label, 0, y + (stacked ? 9 : 12));
    const p = position(c);
    ctx.fillStyle = col[c.status] || css("--text-3");
    ctx.fillRect(x0, y + barY, Math.max(2, X(p) - x0), 10);
    const a = afterBy[c.key];
    const pa = a ? position(a) : null;
    if (pa != null && Math.abs(pa - p) > 0.004) {          // the fixed engine, as a thin bar under it
      ctx.fillStyle = col[a.status] || css("--text-3");
      ctx.globalAlpha = 0.85; ctx.fillRect(x0, y + barY + 13, Math.max(2, X(pa) - x0), 4); ctx.globalAlpha = 1;
    }
    ctx.fillStyle = css("--text-2"); ctx.textAlign = "left";
    ctx.fillText(`${sig(c.value)}${unit(c.unit)}`, x1 + 8, y + barY + 9);
  });
}

function interp(xs, ys, x) {
  for (let i = 1; i < xs.length; i++) {
    const a = xs[i - 1], b = xs[i];
    if ((x >= Math.min(a, b) && x <= Math.max(a, b)) && ys[i - 1] != null && ys[i] != null) {
      const t = b === a ? 0 : (x - a) / (b - a);
      return ys[i - 1] + t * (ys[i] - ys[i - 1]);
    }
  }
  return null;
}

function drawProof(canvas, pr) {
  const { ctx, w, h } = canvasCtx(canvas, 230);
  const L = 56, R = 52, T = 14, B = 34;
  const xs = pr.x, ys = pr.metric;
  const vals = ys.filter((v) => v != null).concat([pr.limit, pr.caution].filter((v) => v != null));
  let ylo = Math.min(...vals), yhi = Math.max(...vals);
  const pad = (yhi - ylo) * 0.1 || 1; ylo -= pad; yhi += pad;
  const xlo = Math.min(...xs), xhi = Math.max(...xs);
  const X = (x) => L + ((x - xlo) / (xhi - xlo || 1)) * (w - L - R);
  const Y = (y) => T + (1 - (y - ylo) / (yhi - ylo || 1)) * (h - T - B);

  // grid and axes
  ctx.strokeStyle = css("--line"); ctx.lineWidth = 1; ctx.fillStyle = css("--text-3"); ctx.textAlign = "right";
  for (const t of ticks(ylo, yhi)) {
    ctx.beginPath(); ctx.moveTo(L, Y(t)); ctx.lineTo(w - R, Y(t)); ctx.stroke();
    ctx.fillText(sig(t), L - 6, Y(t) + 4);
  }
  ctx.textAlign = "center";
  for (const t of ticks(xlo, xhi)) ctx.fillText(sig(t), X(t), h - B + 16);
  ctx.fillText(`${pr.lever_label}${pr.lever_unit ? ` (${pr.lever_unit})` : ""}`, (L + w - R) / 2, h - 4);
  ctx.save(); ctx.translate(12, (T + h - B) / 2); ctx.rotate(-Math.PI / 2);
  ctx.fillText(`${pr.metric_label}${pr.metric_unit ? ` (${pr.metric_unit})` : ""}`.slice(0, 40), 0, 0); ctx.restore();

  // the side of the limit that fails, shaded
  if (pr.limit != null) {
    const failsAbove = pr.caution != null ? pr.limit > pr.caution : true;
    ctx.fillStyle = "rgba(217,118,112,0.08)";
    if (failsAbove) ctx.fillRect(L, T, w - L - R, Math.max(0, Y(pr.limit) - T));
    else ctx.fillRect(L, Y(pr.limit), w - L - R, Math.max(0, h - B - Y(pr.limit)));
    ctx.strokeStyle = css("--err"); ctx.setLineDash([]);
    ctx.beginPath(); ctx.moveTo(L, Y(pr.limit)); ctx.lineTo(w - R, Y(pr.limit)); ctx.stroke();
    ctx.fillStyle = css("--err"); ctx.textAlign = "left"; ctx.fillText("limit", L + 4, Y(pr.limit) - 4);
  }
  if (pr.caution != null) {
    ctx.strokeStyle = css("--warn"); ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(L, Y(pr.caution)); ctx.lineTo(w - R, Y(pr.caution)); ctx.stroke();
    ctx.setLineDash([]); ctx.fillStyle = css("--warn"); ctx.textAlign = "left"; ctx.fillText("caution", L + 4, Y(pr.caution) - 4);
  }

  // brake power on its own axis, so the cost of the cure is on the same graph
  const pw = pr.brake_power_kW.filter((v) => v != null);
  if (pw.length > 1) {
    const plo = Math.min(...pw) * 0.95, phi = Math.max(...pw) * 1.05;
    const P = (v) => T + (1 - (v - plo) / (phi - plo || 1)) * (h - T - B);
    ctx.strokeStyle = css("--text-3"); ctx.lineWidth = 1.2; ctx.setLineDash([2, 3]); ctx.beginPath();
    xs.forEach((x, i) => { const v = pr.brake_power_kW[i]; if (v == null) return; i ? ctx.lineTo(X(x), P(v)) : ctx.moveTo(X(x), P(v)); });
    ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = css("--text-3"); ctx.textAlign = "left";
    for (const t of ticks(plo, phi, 4)) ctx.fillText(n(t, 0), w - R + 6, P(t) + 4);
    ctx.save(); ctx.translate(w - 8, (T + h - B) / 2); ctx.rotate(Math.PI / 2); ctx.textAlign = "center";
    ctx.fillText("brake power (kW)", 0, 0); ctx.restore();
  }

  // the metric itself
  ctx.strokeStyle = css("--accent"); ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.beginPath();
  let started = false;
  xs.forEach((x, i) => { const v = ys[i]; if (v == null) return; started ? ctx.lineTo(X(x), Y(v)) : ctx.moveTo(X(x), Y(v)); started = true; });
  ctx.stroke();
  ctx.fillStyle = css("--accent");
  xs.forEach((x, i) => { if (ys[i] != null) { ctx.beginPath(); ctx.arc(X(x), Y(ys[i]), 2.2, 0, 7); ctx.fill(); } });

  // current and recommended engines
  for (const [x, colr, label] of [[pr.current_x, css("--err"), "as built"], [pr.recommended_x, css("--ok"), "recommended"]]) {
    const v = interp(xs, ys, x);
    if (v == null) continue;
    ctx.strokeStyle = colr; ctx.lineWidth = 1; ctx.setLineDash([2, 3]);
    ctx.beginPath(); ctx.moveTo(X(x), T); ctx.lineTo(X(x), h - B); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = colr; ctx.beginPath(); ctx.arc(X(x), Y(v), 5, 0, 7); ctx.fill();
    ctx.strokeStyle = css("--surface", "#000"); ctx.lineWidth = 2; ctx.stroke();
    ctx.textAlign = X(x) > w * 0.75 ? "right" : "left";
    ctx.fillText(label, X(x) + (ctx.textAlign === "right" ? -8 : 8), Y(v) - 8);
  }
}

const COST_ALPHA = [0.95, 0.75, 0.58, 0.45, 0.35, 0.27, 0.2, 0.14];
function drawCost(canvas, before, after) {
  const items = [...new Set([...before.breakdown, ...(after ? after.breakdown : [])].map((l) => l.item))];
  const bars = after ? [["As built", before, 18], ["Recommended", after, 58]] : [["As built", before, 18]];
  const { ctx, w, h } = canvasCtx(canvas, after ? 120 : 80);
  const L = 92, R = 30, max = Math.max(before.build_cost_index, after ? after.build_cost_index : 0, 100) * 1.08;
  const X = (v) => L + (v / max) * (w - L - R);
  bars.forEach(([label, rep, y]) => {
    ctx.fillStyle = css("--text-2"); ctx.textAlign = "left"; ctx.fillText(label, 0, y + 14);
    let acc = 0;
    items.forEach((it, i) => {
      const line = rep.breakdown.find((l) => l.item === it);
      if (!line) return;
      ctx.globalAlpha = COST_ALPHA[i % COST_ALPHA.length]; ctx.fillStyle = css("--accent");
      ctx.fillRect(X(acc), y, Math.max(1, X(acc + line.points) - X(acc) - 1), 22); ctx.globalAlpha = 1;
      acc += line.points;
    });
    ctx.fillStyle = css("--text"); ctx.fillText(n(rep.build_cost_index, 0), X(acc) + 6, y + 15);
  });
  ctx.strokeStyle = css("--text-3"); ctx.setLineDash([2, 3]);
  ctx.beginPath(); ctx.moveTo(X(100), 8); ctx.lineTo(X(100), h - 32); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = css("--text-3"); ctx.textAlign = "center"; ctx.fillText("baseline 100", X(100), h - 16);
  return items;
}

/* ---------- report ---------- */
function checkRows(checks) {
  return checks.map((c) => `
    <tr class="st-${c.status.replace("/", "")}">
      <td><b>${esc(c.label)}</b><span class="fe-basis">${esc(c.basis)}</span></td>
      <td class="num">${c.kind === "flag" ? (c.value ? "yes" : "no") : `${sig(c.value)}${unit(c.unit)}`}</td>
      <td class="num">${c.caution == null ? "" : `${c.kind === "max" ? "≤" : "≥"} ${sig(c.caution)}`}</td>
      <td class="num">${c.limit == null || c.kind === "flag" ? "" : `${c.kind === "max" ? "≤" : "≥"} ${sig(c.limit)}`}</td>
      <td class="num">${c.margin_percent == null ? "" : `${n(c.margin_percent, 0)}%`}</td>
      <td><span class="fe-pill st-${c.status.replace("/", "")}">${STATUS_WORD[c.status]}</span></td>
    </tr>`).join("");
}

function snapshotRows(b, a) {
  const rows = [
    ["Brake power", b.brake_power_kW, a.brake_power_kW, "kW", 1],
    ["Brake torque", b.brake_torque_Nm, a.brake_torque_Nm, "N·m", 0],
    ["BMEP", b.bmep_bar, a.bmep_bar, "bar", 1],
    ["Brake thermal efficiency", b.brake_thermal_efficiency * 100, a.brake_thermal_efficiency * 100, "%", 1],
    ["BSFC", b.bsfc_g_per_kWh, a.bsfc_g_per_kWh, "g/kWh", 0],
    ["Peak cylinder pressure", b.peak_pressure_bar, a.peak_pressure_bar, "bar", 0],
  ];
  return rows.map(([k, x, y, u, d]) => {
    const ch = x ? (y / x - 1) * 100 : 0;
    return `<tr><td>${k}</td><td class="num">${n(x, d)} ${u}</td><td class="num">${n(y, d)} ${u}</td>
      <td class="num ${Math.abs(ch) < 0.05 ? "" : ch > 0 ? "up" : "down"}">${Math.abs(ch) < 0.05 ? "unchanged" : `${ch > 0 ? "+" : ""}${n(ch, 1)}%`}</td></tr>`;
  }).join("");
}

function costTable(b, a, compare) {
  const rows = [
    ["Build cost index", b.build_cost_index, a.build_cost_index, "", 0],
    ["Build cost per kW (index)", b.cost_index_per_kW, a.cost_index_per_kW, "× baseline", 2],
    ["Fuel flow", b.fuel_L_per_h, a.fuel_L_per_h, "L/h", 1],
    ["Fuel cost", b.fuel_cost_gbp_per_h, a.fuel_cost_gbp_per_h, "£/h", 2],
    ["Fuel cost per kWh delivered", b.fuel_cost_gbp_per_kWh, a.fuel_cost_gbp_per_kWh, "£/kWh", 3],
    ["Fuel cost per 1000 h", b.fuel_cost_gbp_per_1000h, a.fuel_cost_gbp_per_1000h, "£", 0],
  ];
  // Pounds lead the number; every other unit follows it.
  const v = (x, u, d) => (u.startsWith("£") ? `£${n(x, d)}${u.slice(1)}` : `${n(x, d)} ${u}`.trim());
  return rows.map(([k, x, y, u, d]) =>
    `<tr><td>${k}</td><td class="num">${v(x, u, d)}</td>${compare ? `<td class="num">${v(y, u, d)}</td>` : ""}</tr>`).join("");
}

function render(root, r) {
  const changed = r.recommendations.filter((x) => x.resolved);
  const open = r.recommendations.filter((x) => !x.resolved);
  root.innerHTML = `
    <div class="fe-verdict v-${r.verdict}">
      <span class="fe-verdict-word">${VERDICT_WORD[r.verdict]}</span>
      <p class="fe-headline">${esc(r.headline)}</p>
      ${r.summary && r.summary !== r.headline ? `<p class="fe-summary">${esc(r.summary)}</p>` : ""}
    </div>

    <h3 class="fe-h">Design envelope</h3>
    <p class="fe-cap">Each bar is one criterion, scaled so its caution threshold sits on the dashed line and its limit on
      the solid line; anything in the red zone fails. ${changed.length ? "The thin bar under each is the engine after the recommended changes." : ""}
      Actual values are printed on the right and in the table below.</p>
    <canvas class="fe-canvas" id="feEnvelope"></canvas>

    <div class="fe-table-wrap"><table class="fe-table">
      <thead><tr><th>Criterion and basis</th><th>Value</th><th>Caution</th><th>Limit</th><th>Margin</th><th>Status</th></tr></thead>
      <tbody>${checkRows(r.checks)}</tbody></table></div>

    ${changed.length || open.length ? `<h3 class="fe-h">Recommended changes</h3>
    <p class="fe-cap">Failures are cured one at a time, most severe first. Each change is the smallest move of one design
      lever that brings its check back inside the design envelope, found by bisecting the solver; the engine is then
      re-solved before the next. The graphs are solver sweeps of that lever, not sketches.</p>` : ""}
    ${changed.map((x, i) => `
      <div class="fe-step">
        <p class="fe-step-head"><span>Step ${x.step}</span><b>${esc(x.check_label)}</b>
          <em>${esc(x.lever_label)}: ${lever(x.from_value, x.lever)} → ${lever(x.to_value, x.lever)}</em></p>
        <p class="fe-step-why">${esc(x.rationale)}${x.brake_power_change_percent != null
          ? ` Brake power ${x.brake_power_change_percent >= 0 ? "+" : ""}${n(x.brake_power_change_percent, 1)}% at this step.` : ""}</p>
        <canvas class="fe-canvas" data-proof="${i}"></canvas>
      </div>`).join("")}
    ${open.map((x) => `<p class="fe-open"><b>${esc(x.check_label || x.check_key)}</b> ${esc(x.rationale)}</p>`).join("")}

    ${changed.length ? `
    <h3 class="fe-h">Verified result</h3>
    <p class="fe-cap">The recommended engine, solved from scratch: <b>${VERDICT_WORD[r.verified_verdict].toLowerCase()}</b>.</p>
    <div class="fe-table-wrap"><table class="fe-table fe-compact">
      <thead><tr><th></th><th>As built</th><th>Recommended</th><th>Change</th></tr></thead>
      <tbody>${snapshotRows(r.before, r.after)}</tbody></table></div>` : ""}

    <h3 class="fe-h">Cost</h3>
    <p class="fe-cap">Build cost is a relative index: a 2.0 L naturally aspirated petrol inline-4 scores 100. It ranks
      configurations from the declared coefficients below and is not a price. Fuel cost is computed from this operating
      point's BSFC and brake power at an assumed pump price of £${n(r.cost_before.fuel_price_gbp_per_L, 2)}/L.</p>
    <canvas class="fe-canvas" id="feCost"></canvas>
    <div class="fe-legend" id="feCostLegend"></div>
    <div class="fe-table-wrap"><table class="fe-table fe-compact">
      <thead><tr><th></th><th>As built</th>${changed.length ? "<th>Recommended</th>" : ""}</tr></thead>
      <tbody>${costTable(r.cost_before, r.cost_after, changed.length > 0)}</tbody></table></div>
    <details class="fe-details"><summary>Cost breakdown and coefficients</summary>
      <div class="fe-table-wrap"><table class="fe-table fe-compact">
        <thead><tr><th>Item</th><th>Index points</th><th>Basis</th></tr></thead>
        <tbody>${r.cost_before.breakdown.map((l) => `<tr><td>${esc(l.item)}</td><td class="num">${n(l.points, 1)}</td><td>${esc(l.basis)}</td></tr>`).join("")}</tbody>
      </table></div></details>

    <details class="fe-details"><summary>Assumptions</summary>
      <ul>${r.assumptions.map((a) => `<li>${esc(a)}</li>`).join("")}</ul></details>
    <p class="fe-foot">${r.solves} solver runs.</p>`;
  draw(root, r);
}

function draw(root, r) {
  const env = root.querySelector("#feEnvelope");
  if (env) drawEnvelope(env, r.checks, r.recommendations.some((x) => x.resolved) ? r.verified_checks : null);
  const changed = r.recommendations.filter((x) => x.resolved);
  root.querySelectorAll("canvas[data-proof]").forEach((c) => {
    const rec = changed[Number(c.dataset.proof)];
    const pr = r.proofs.find((p) => p.metric_key === rec.check_key && p.lever === rec.lever);
    if (pr) drawProof(c, pr);
  });
  const cost = root.querySelector("#feCost");
  if (cost) {
    const items = drawCost(cost, r.cost_before, changed.length ? r.cost_after : null);
    const leg = root.querySelector("#feCostLegend");
    if (leg) leg.innerHTML = items.map((it, i) =>
      `<span><i style="opacity:${COST_ALPHA[i % COST_ALPHA.length]}"></i>${esc(it)}</span>`).join("");
  }
}

/** Run the analysis on a /piston/simulate payload and show it in `root`. */
export async function runFeasibility(payload, root, statusEl) {
  if (!root) return;
  const body = { ...payload, include_trace: false };
  root.classList.remove("is-stale");
  root.innerHTML = `<p class="fe-busy">Analysing: solving the engine, then searching and re-solving for each fix…</p>`;
  if (statusEl) statusEl.disabled = true;
  try {
    const res = await fetch(API, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Analysis failed (${res.status})`);
    lastReport = data;
    render(root, data);
  } catch (err) {
    root.innerHTML = `<p class="fe-error">Could not analyse this engine: ${esc(err.message)}</p>`;
  } finally {
    if (statusEl) statusEl.disabled = false;
  }
}

/** Inputs moved after the analysis: say so rather than show a stale verdict. */
export function markStale(root) {
  if (!root || !lastReport || root.classList.contains("is-stale")) return;
  root.classList.add("is-stale");
  root.insertAdjacentHTML("afterbegin",
    `<p class="fe-stale">The inputs have changed since this analysis. Run it again to judge the engine as it is now.</p>`);
}

let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    const root = document.getElementById("feasReport");
    if (root && lastReport && !root.querySelector(".fe-busy")) draw(root, lastReport);
  }, 150);
});

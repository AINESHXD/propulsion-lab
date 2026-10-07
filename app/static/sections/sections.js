/**
 * Engine cross-section pages: loads the generated SVG and its solver metadata,
 * then wires the colour-mode toggle, legend, stats, station table and tooltips.
 * Geometry comes from scripts/build_engine_sections.py; re-run it and bump ?v= / ASSET_V.
 */
const ASSET_V = "?v=2";
const ENGINE = document.body.dataset.engine || "turbojet";

const host = document.getElementById("section-host");
const tip = document.getElementById("tip");
const fmt = (v, d = 0) => Number(v).toLocaleString("en-GB", { maximumFractionDigits: d, minimumFractionDigits: d });

function cssGradient(map) {
  return `linear-gradient(90deg, ${map.map(([t, c]) => `${c} ${(t * 100).toFixed(0)}%`).join(", ")})`;
}

async function load() {
  const [svgText, meta] = await Promise.all([
    fetch(`/lab/sections/${ENGINE}.svg${ASSET_V}`).then((r) => { if (!r.ok) throw new Error(r.status); return r.text(); }),
    fetch(`/lab/sections/${ENGINE}.json${ASSET_V}`).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
  ]);
  host.innerHTML = svgText;
  const svg = host.querySelector("svg");
  setupModes(svg, meta);
  setupStats(meta);
  setupStations(svg);
  setupTooltips(svg);
}

function setupModes(svg, meta) {
  const legend = document.getElementById("legend");
  const lo = document.getElementById("legend-lo"), hi = document.getElementById("legend-hi");
  const bar = document.getElementById("legend-bar");
  const apply = (mode) => {
    svg.classList.remove("mode-temp", "mode-pres", "mode-off");
    svg.classList.add(`mode-${mode}`);
    document.querySelectorAll(".seg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
    legend.hidden = mode === "off";
    if (mode === "temp") {
      const [a, b] = meta.temperature_range_K;
      lo.textContent = `${fmt(a)} K`; hi.textContent = `${fmt(b)} K`; bar.style.background = cssGradient(meta.temp_colormap);
    } else if (mode === "pres") {
      const [a, b] = meta.pressure_range_Pa;
      lo.textContent = `${fmt(a / 1000)} kPa`; hi.textContent = `${fmt(b / 1000)} kPa`; bar.style.background = cssGradient(meta.pres_colormap);
    }
  };
  document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => apply(b.dataset.mode)));
  apply("temp");
}

function setupStats(meta) {
  const op = meta.operating_point;
  const stats = [
    ["Thrust", `${fmt(meta.thrust_kN, 1)} kN`],
    ["TSFC", `${fmt(meta.TSFC_kg_per_kN_hr, 1)} kg/(kN·h)`],
    ["Jet velocity", `${fmt(meta.exit_velocity_m_s)} m/s`],
    ["Operating point", `${fmt(op.altitude_m / 1000)} km · M${op.mach}`],
  ];
  document.getElementById("stats").innerHTML = stats
    .map(([k, v]) => `<div class="card stat"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
}

function setupStations(svg) {
  const rows = document.getElementById("station-rows");
  const groups = [...svg.querySelectorAll(".station")];
  rows.innerHTML = groups.map((g) => {
    const d = g.dataset;
    return `<tr data-station="${d.station}"><td class="num" style="text-align:left">${d.station}</td><td>${d.name}</td>` +
      `<td class="num">${fmt(d.t0)}</td><td class="num">${fmt(d.p0 / 1000, 1)}</td></tr>`;
  }).join("");
  const link = (key, on) => {
    svg.querySelector(`.station[data-station="${key}"]`)?.classList.toggle("active", on);
    rows.querySelector(`tr[data-station="${key}"]`)?.classList.toggle("hl", on);
  };
  groups.forEach((g) => {
    ["mouseenter", "focus"].forEach((e) => g.addEventListener(e, () => link(g.dataset.station, true)));
    ["mouseleave", "blur"].forEach((e) => g.addEventListener(e, () => link(g.dataset.station, false)));
  });
  rows.querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("mouseenter", () => link(tr.dataset.station, true));
    tr.addEventListener("mouseleave", () => link(tr.dataset.station, false));
  });
}

function setupTooltips(svg) {
  const figure = host.parentElement;
  const show = (el, html) => {
    tip.innerHTML = html;
    tip.hidden = false;
    const f = figure.getBoundingClientRect(), r = el.getBoundingClientRect();
    const x = Math.min(Math.max(r.left + r.width / 2 - f.left - tip.offsetWidth / 2, 8), f.width - tip.offsetWidth - 8);
    let y = r.top - f.top - tip.offsetHeight - 10;
    if (y < 4) y = r.bottom - f.top + 10;
    tip.style.left = `${x}px`; tip.style.top = `${y}px`;
  };
  const hide = () => { tip.hidden = true; };
  svg.querySelectorAll(".component").forEach((g) => {
    const html = `<b>${g.dataset.name}</b>${g.dataset.text}`;
    ["mouseenter", "focus"].forEach((e) => g.addEventListener(e, () => { g.classList.add("active"); show(g, html); }));
    ["mouseleave", "blur"].forEach((e) => g.addEventListener(e, () => { g.classList.remove("active"); hide(); }));
  });
  svg.querySelectorAll(".station").forEach((g) => {
    const d = g.dataset;
    const html = `<b>Station ${d.station} &middot; ${d.name}</b>` +
      `<span class="m">T<sub>0</sub> ${fmt(d.t0)} K &nbsp; p<sub>0</sub> ${fmt(d.p0 / 1000, 1)} kPa</span>`;
    ["mouseenter", "focus"].forEach((e) => g.addEventListener(e, () => show(g.querySelector(".station-dot"), html)));
    ["mouseleave", "blur"].forEach((e) => g.addEventListener(e, hide));
  });
  // Touch: tapping outside any target dismisses an open tooltip.
  document.addEventListener("pointerdown", (e) => { if (!e.target.closest(".component, .station")) hide(); });
}

load().catch((err) => {
  host.innerHTML = `<div class="loading">Cross-section failed to load (${err.message}).</div>`;
});

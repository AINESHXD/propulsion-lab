/* PropulsionLab guided tour.
 *
 * A dependency-free product tour: a spotlight overlay dims the page, highlights
 * one element at a time, and explains it. Auto-runs once for first-time visitors
 * (localStorage flag) and can be replayed from the "Tutorial" button in the top
 * bar. Fully self-contained — injects its own styles and DOM.
 */
(function () {
  "use strict";

  const SEEN_KEY = "pl_tour_seen_v2";

  // Each step anchors to a CSS selector (or is centered). `tab` switches the
  // console to that tab first. Missing anchors are skipped gracefully.
  const STEPS = [
    {
      center: true,
      title: "Welcome to PropulsionLab",
      body: "A browser tool that runs real reduced-order gas-turbine cycles — five engine families, station by station. Here's a 90-second tour of everything it does. You can skip anytime.",
    },
    {
      sel: ".engine-card-grid",
      title: "1 · Pick an engine family",
      body: "Turbojet, turbofan, turboprop, ramjet or scramjet. Each card loads its own physics solver and input set.",
    },
    {
      sel: "#presetSelect",
      title: "2 · Start from a real engine",
      body: "Load a public-data preset (CFM56, J85, …) as a starting design point — or just tweak the sensible defaults yourself.",
    },
    {
      sel: "#simulationForm",
      title: "3 · Set the design point",
      body: "Altitude, Mach, pressure ratio, turbine-inlet temperature, component efficiencies — every assumption is exposed. Hover any “?” for a plain-English explanation.",
    },
    {
      sel: "#runSimulationButton",
      title: "4 · Run the cycle",
      body: "Solves the complete station-by-station cycle in milliseconds. It also re-runs automatically whenever you change an input.",
    },
    {
      sel: ".results-panel .metric-grid",
      title: "5 · Read the performance",
      body: "Thrust, TSFC (how thirsty it is), and thermal / propulsive / overall efficiency — the headline numbers for this design.",
    },
    {
      sel: ".results-panel .table-wrap",
      title: "6 · Station by station",
      body: "Total and static temperature, pressure, Mach and velocity at every station from the inlet to the nozzle exit.",
    },
    {
      sel: "#cycleInsights",
      title: "7 · Plain-English insights",
      body: "The raw numbers translated into what they mean — compressor work, nozzle choking, expansion state — refreshed every run.",
    },
    {
      sel: "#emissionsPanel",
      title: "8 · Combustor emissions",
      body: "A Cantera reactor-network estimate of NOx and CO, plus an ICAO landing–takeoff NOx total. High-pressure-ratio cores make more NOx — try it.",
    },
    {
      sel: ".console-tabs",
      title: "9 · Go deeper",
      body: "Sweep a parameter, compare engines side by side, match the off-design operating line, fly a multi-leg mission, read a compressor map, or run a genetic-algorithm design optimization.",
    },
    {
      sel: 'a[href="/lab/viewer3d.html"]',
      title: "10 · 3D engine viewer",
      body: "Interactive Blender-built cutaways of all five families, with hover-to-explain station labels.",
    },
    {
      sel: 'a[href="/lab/mlsuite.html"]',
      title: "11 · ML Suite",
      body: "A from-scratch neural network that predicts performance instantly in your browser — and verifies itself live against the exact physics.",
    },
    {
      sel: "#shareLinkButton",
      title: "12 · Share & export",
      body: "Your whole input deck encodes into a shareable link. You can also export a runnable Python script or a branded PDF report.",
    },
    {
      center: true,
      title: "That's the tour 🚀",
      body: "Replay it anytime from “Tutorial” in the top bar. Now go design an engine — start by hitting Run cycle.",
    },
  ];

  let i = 0;
  let active = false;
  let els = null;

  function injectStyles() {
    if (document.getElementById("tourStyles")) return;
    const css = `
      #tourBackdrop{position:fixed;inset:0;z-index:9000;pointer-events:auto;background:transparent;}
      #tourHi{position:fixed;z-index:9001;border-radius:12px;pointer-events:none;
        box-shadow:0 0 0 9999px rgba(7,8,11,.76),0 0 0 2px var(--accent,#7ba7eb),0 0 26px rgba(123,167,235,.5);
        transition:top .25s ease,left .25s ease,width .25s ease,height .25s ease;}
      #tourHi.center{opacity:0;}
      #tourTip{position:fixed;z-index:9002;width:330px;max-width:calc(100vw - 28px);
        background:rgba(18,20,25,.97);border:1px solid rgba(255,255,255,.16);border-radius:14px;
        padding:16px 18px;box-shadow:0 18px 50px rgba(0,0,0,.55);backdrop-filter:blur(12px);
        color:#f3f4f6;font:14px/1.55 -apple-system,BlinkMacSystemFont,"Inter",system-ui,sans-serif;}
      #tourTip.center{left:50%;top:50%;transform:translate(-50%,-50%);width:420px;text-align:center;}
      #tourTip h3{margin:0 0 8px;font-size:1rem;font-weight:650;letter-spacing:-.01em;}
      #tourTip p{margin:0 0 14px;color:#c4c8ce;font-size:.86rem;}
      #tourTip .row{display:flex;align-items:center;justify-content:space-between;gap:10px;}
      #tourTip .count{font-family:ui-monospace,monospace;font-size:.7rem;color:#9197a1;letter-spacing:.08em;}
      #tourTip .acts{display:flex;gap:8px;}
      #tourTip button{font:inherit;font-size:.8rem;border-radius:9px;padding:7px 14px;cursor:pointer;border:1px solid rgba(255,255,255,.18);
        background:#16181d;color:#f3f4f6;transition:border-color .15s,color .15s,background .15s;}
      #tourTip button:hover{border-color:#7ba7eb;color:#fff;}
      #tourTip button.primary{background:rgba(123,167,235,.16);border-color:#7ba7eb;color:#cfe0ff;}
      #tourTip .skip{background:none;border:none;color:#9197a1;padding:7px 4px;}
      #tourTip .skip:hover{color:#f3f4f6;}
      @media(prefers-reduced-motion:reduce){#tourHi{transition:none;}}
    `;
    const s = document.createElement("style");
    s.id = "tourStyles"; s.textContent = css; document.head.appendChild(s);
  }

  function buildDom() {
    const backdrop = document.createElement("div"); backdrop.id = "tourBackdrop";
    const hi = document.createElement("div"); hi.id = "tourHi";
    const tip = document.createElement("div"); tip.id = "tourTip";
    tip.innerHTML =
      `<h3 data-t></h3><p data-b></p>` +
      `<div class="row"><span class="count" data-c></span>` +
      `<div class="acts"><button class="skip" data-skip>Skip</button>` +
      `<button data-back>Back</button><button class="primary" data-next>Next</button></div></div>`;
    document.body.appendChild(backdrop);
    document.body.appendChild(hi);
    document.body.appendChild(tip);
    backdrop.addEventListener("click", end);
    tip.querySelector("[data-skip]").addEventListener("click", end);
    tip.querySelector("[data-back]").addEventListener("click", () => go(i - 1));
    tip.querySelector("[data-next]").addEventListener("click", () => go(i + 1));
    return { backdrop, hi, tip };
  }

  function activateTabFor(step) {
    if (!step.tab) return;
    const btn = document.querySelector(`.tab-button[data-tab="${step.tab}"]`);
    if (btn) btn.click();
  }

  function place(step) {
    const hi = els.hi, tip = els.tip;
    tip.querySelector("[data-t]").textContent = step.title;
    tip.querySelector("[data-b]").textContent = step.body;
    tip.querySelector("[data-c]").textContent = `${i + 1} / ${STEPS.length}`;
    tip.querySelector("[data-back]").style.visibility = i === 0 ? "hidden" : "visible";
    tip.querySelector("[data-next]").textContent = i === STEPS.length - 1 ? "Done" : "Next";

    const target = step.center ? null : document.querySelector(step.sel);
    if (!target) {                                  // centered (or anchor missing)
      hi.classList.add("center"); tip.classList.add("center");
      tip.style.left = ""; tip.style.top = "";
      return;
    }
    hi.classList.remove("center"); tip.classList.remove("center");
    const r = target.getBoundingClientRect();
    const pad = 6;
    hi.style.top = `${r.top - pad}px`;
    hi.style.left = `${r.left - pad}px`;
    hi.style.width = `${r.width + pad * 2}px`;
    hi.style.height = `${r.height + pad * 2}px`;

    const tipW = tip.offsetWidth || 330, tipH = tip.offsetHeight || 150;
    const vw = window.innerWidth, vh = window.innerHeight;
    let top = r.bottom + 12;
    if (top + tipH > vh - 10) top = r.top - tipH - 12;       // flip above
    if (top < 10) top = Math.min(vh - tipH - 10, Math.max(10, r.bottom + 12));
    let left = r.left + r.width / 2 - tipW / 2;
    left = Math.max(12, Math.min(left, vw - tipW - 12));
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
  }

  function go(n) {
    if (n < 0) return;
    if (n >= STEPS.length) return end();
    i = n;
    const step = STEPS[i];
    activateTabFor(step);
    const target = step.center ? null : document.querySelector(step.sel);
    if (target) {
      target.scrollIntoView({ block: "center", behavior: "smooth" });
      setTimeout(() => place(step), 360);
    } else {
      place(step);
    }
  }

  function reposition() { if (active) place(STEPS[i]); }

  function start() {
    if (active) return;
    injectStyles();
    els = buildDom();
    active = true;
    // NB: do not set body overflow:hidden — it would stop scrollIntoView from
    // reaching steps below the fold. The backdrop blocks stray clicks instead.
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    document.addEventListener("keydown", onKey, true);
    go(0);
  }

  function end() {
    if (!active) return;
    active = false;
    window.removeEventListener("resize", reposition);
    window.removeEventListener("scroll", reposition, true);
    document.removeEventListener("keydown", onKey, true);
    [els.backdrop, els.hi, els.tip].forEach((e) => e && e.remove());
    els = null;
    try { localStorage.setItem(SEEN_KEY, "1"); } catch (e) { /* ignore */ }
  }

  function onKey(e) {
    if (e.key === "Escape") { e.preventDefault(); end(); }
    else if (e.key === "ArrowRight" || e.key === "Enter") { e.preventDefault(); go(i + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(i - 1); }
  }

  // Expose + wire the launch button; auto-run once for new visitors.
  window.PLTour = { start, end };
  function boot() {
    const btn = document.getElementById("tutorialButton");
    if (btn) btn.addEventListener("click", (e) => { e.preventDefault(); start(); });
    let seen = false;
    try { seen = localStorage.getItem(SEEN_KEY) === "1"; } catch (e) { /* ignore */ }
    if (!seen) setTimeout(start, 1400);     // let the boot screen settle first
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();

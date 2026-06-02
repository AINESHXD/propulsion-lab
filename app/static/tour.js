/* PropulsionLab guided tour — a dependency-free spotlight walkthrough.
 * Auto-runs once for new visitors; replay from the "Tutorial" button up top. */
(function () {
  "use strict";

  const SEEN_KEY = "pl_tour_seen_v3";

  // Each step anchors to a selector (or is centered). Missing anchors are skipped.
  const STEPS = [
    {
      center: true,
      title: "Welcome to PropulsionLab",
      body: "This runs real jet-engine cycles in your browser — five engine types, every station. Want the quick tour? You can skip whenever.",
    },
    { sel: ".engine-card-grid", title: "Pick an engine",
      body: "Turbojet, turbofan, turboprop, ramjet, scramjet. Each one loads its own solver and inputs." },
    { sel: "#presetSelect", title: "Or start from a real one",
      body: "Load a known engine like the CFM56 or J85 as your starting point, then change whatever you want." },
    { sel: "#simulationForm", title: "Set the design point",
      body: "Altitude, speed, pressure ratio, turbine temperature, efficiencies. Nothing's hidden — hover a “?” if a field is new to you." },
    { sel: "#runSimulationButton", title: "Run it",
      body: "Solves the whole cycle in a few milliseconds, and re-runs on its own as you edit the inputs." },
    { sel: ".results-panel .metric-grid", title: "The headline numbers",
      body: "Thrust, fuel burn (TSFC) and efficiency — what actually matters for the design." },
    { sel: ".results-panel .table-wrap", title: "Every station",
      body: "Temperature, pressure, Mach and velocity from the inlet all the way to the nozzle." },
    { sel: "#cycleInsights", title: "In plain English",
      body: "The same numbers, explained — what the compressor's doing, whether the nozzle's choked, and why." },
    { sel: "#emissionsPanel", title: "Emissions",
      body: "A real NOx and CO estimate from combustion chemistry, plus the ICAO landing-takeoff total. Push the pressure ratio up and watch NOx climb." },
    { sel: ".console-tabs", title: "Go further",
      body: "Sweep a parameter, compare engines, run them off-design, fly a mission, read a compressor map, or let a genetic algorithm optimize the design. Each tab has an “ⓘ” that explains it." },
    { sel: 'a[href="/lab/viewer3d.html"]', title: "See it in 3D",
      body: "Spin through cutaways of all five engines, with a label on every stage." },
    { sel: 'a[href="/lab/mlsuite.html"]', title: "The ML side",
      body: "A neural net that predicts performance instantly — and checks itself against the real physics." },
    { sel: "#shareLinkButton", title: "Share and export",
      body: "Your setup lives in the URL. You can also export a Python script or a PDF." },
    { center: true, title: "That's the tour",
      body: "Replay it anytime from Tutorial up top. Go build something." },
  ];

  let i = 0, active = false, els = null;

  function injectStyles() {
    if (document.getElementById("tourStyles")) return;
    const css = `
      #tourBackdrop{position:fixed;inset:0;z-index:9000;background:transparent;
        opacity:0;transition:opacity .3s ease;}
      #tourBackdrop.in{opacity:1;}
      #tourHi{position:fixed;z-index:9001;border-radius:14px;pointer-events:none;
        box-shadow:0 0 0 9999px rgba(7,8,11,.72), 0 0 0 1.5px rgba(123,167,235,.9), 0 0 30px rgba(123,167,235,.45);
        transition:opacity .2s ease;}
      #tourHi.center{opacity:0;}
      #tourTip{position:fixed;z-index:9002;width:340px;max-width:calc(100vw - 28px);
        background:linear-gradient(180deg,rgba(22,24,30,.98),rgba(15,17,21,.98));
        border:1px solid rgba(255,255,255,.12);border-radius:16px;padding:18px 18px 14px;
        box-shadow:0 24px 60px rgba(0,0,0,.6);backdrop-filter:blur(16px);color:#f3f4f6;
        font:14px/1.55 -apple-system,BlinkMacSystemFont,"Inter",system-ui,sans-serif;
        opacity:0;transform:translateY(6px);transition:opacity .24s ease,transform .24s ease;}
      #tourTip.show{opacity:1;transform:translateY(0);}
      #tourTip.center{left:50%;top:50%;width:440px;text-align:center;
        transform:translate(-50%,-50%) scale(.98);}
      #tourTip.center.show{transform:translate(-50%,-50%) scale(1);}
      #tourTip .eyebrow{font:600 .6rem/1 ui-monospace,monospace;letter-spacing:.18em;
        text-transform:uppercase;color:#7ba7eb;margin:0 0 9px;}
      #tourTip h3{margin:0 0 7px;font-size:1.02rem;font-weight:650;letter-spacing:-.01em;}
      #tourTip p{margin:0 0 16px;color:#c2c7cf;font-size:.87rem;}
      #tourTip .foot{display:flex;align-items:center;gap:12px;}
      #tourTip .prog{flex:1;height:3px;border-radius:3px;background:rgba(255,255,255,.12);overflow:hidden;}
      #tourTip .prog i{display:block;height:100%;background:#7ba7eb;border-radius:3px;
        transition:width .3s cubic-bezier(.4,0,.2,1);}
      #tourTip .acts{display:flex;gap:7px;align-items:center;}
      #tourTip button{font:inherit;font-size:.8rem;border-radius:10px;padding:7px 13px;cursor:pointer;
        border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.04);color:#f3f4f6;
        transition:border-color .15s,color .15s,background .15s;}
      #tourTip button:hover{border-color:#7ba7eb;color:#fff;background:rgba(123,167,235,.12);}
      #tourTip button.primary{background:#7ba7eb;border-color:#7ba7eb;color:#0a0b0e;font-weight:600;}
      #tourTip button.primary:hover{background:#9cbcf0;}
      #tourTip button.skip{background:none;border:none;color:#878d97;padding:7px 6px;}
      #tourTip button.skip:hover{color:#f3f4f6;}
      @media(prefers-reduced-motion:reduce){
        #tourHi,#tourTip,#tourBackdrop,#tourTip .prog i{transition:none;}}
    `;
    const s = document.createElement("style");
    s.id = "tourStyles"; s.textContent = css; document.head.appendChild(s);
  }

  function buildDom() {
    const backdrop = document.createElement("div"); backdrop.id = "tourBackdrop";
    const hi = document.createElement("div"); hi.id = "tourHi";
    const tip = document.createElement("div"); tip.id = "tourTip";
    tip.innerHTML =
      `<p class="eyebrow" data-e>Tour</p><h3 data-t></h3><p data-b></p>` +
      `<div class="foot"><div class="prog"><i data-p></i></div>` +
      `<div class="acts"><button class="skip" data-skip>Skip</button>` +
      `<button data-back>Back</button><button class="primary" data-next>Next</button></div></div>`;
    document.body.append(backdrop, hi, tip);
    requestAnimationFrame(() => backdrop.classList.add("in"));
    backdrop.addEventListener("click", end);
    tip.querySelector("[data-skip]").addEventListener("click", end);
    tip.querySelector("[data-back]").addEventListener("click", () => go(i - 1));
    tip.querySelector("[data-next]").addEventListener("click", () => go(i + 1));
    return { backdrop, hi, tip };
  }

  function place(step) {
    const { hi, tip } = els;
    tip.querySelector("[data-e]").textContent = step.center ? "PropulsionLab" : `Step ${i} of ${STEPS.length - 2}`;
    tip.querySelector("[data-t]").textContent = step.title;
    tip.querySelector("[data-b]").textContent = step.body;
    tip.querySelector("[data-p]").style.width = `${(i / (STEPS.length - 1)) * 100}%`;
    tip.querySelector("[data-back]").style.visibility = i === 0 ? "hidden" : "visible";
    tip.querySelector("[data-next]").textContent = i === STEPS.length - 1 ? "Done" : "Next";

    const target = step.center ? null : document.querySelector(step.sel);
    if (!target) {
      hi.classList.add("center"); tip.classList.add("center");
      tip.style.left = ""; tip.style.top = "";
      requestAnimationFrame(() => tip.classList.add("show"));
      return;
    }
    hi.classList.remove("center"); tip.classList.remove("center");
    const r = target.getBoundingClientRect(), pad = 6;
    hi.style.top = `${r.top - pad}px`; hi.style.left = `${r.left - pad}px`;
    hi.style.width = `${r.width + pad * 2}px`; hi.style.height = `${r.height + pad * 2}px`;

    const tipW = tip.offsetWidth || 340, tipH = tip.offsetHeight || 160;
    const vw = innerWidth, vh = innerHeight;
    let top = r.bottom + 14;
    if (top + tipH > vh - 10) top = r.top - tipH - 14;
    if (top < 10) top = Math.max(10, Math.min(vh - tipH - 10, r.bottom + 14));
    let left = Math.max(12, Math.min(r.left + r.width / 2 - tipW / 2, vw - tipW - 12));
    tip.style.left = `${left}px`; tip.style.top = `${top}px`;
    requestAnimationFrame(() => tip.classList.add("show"));
  }

  function go(n) {
    if (n < 0) return;
    if (n >= STEPS.length) return end();
    els.tip.classList.remove("show");          // fade the card out, then back in
    i = n;
    const step = STEPS[i];
    const target = step.center ? null : document.querySelector(step.sel);
    if (target) {
      // Instant scroll, then measure on the next frames so the spotlight snaps
      // to the *settled* position — no gliding across the screen.
      target.scrollIntoView({ block: "center", behavior: "auto" });
      requestAnimationFrame(() => requestAnimationFrame(() => place(step)));
    } else {
      requestAnimationFrame(() => place(step));
    }
  }

  function reposition() { if (active) place(STEPS[i]); }

  function start() {
    if (active) return;
    injectStyles();
    els = buildDom();
    active = true;
    addEventListener("resize", reposition);
    addEventListener("scroll", reposition, true);
    document.addEventListener("keydown", onKey, true);
    go(0);
  }

  function end() {
    if (!active) return;
    active = false;
    removeEventListener("resize", reposition);
    removeEventListener("scroll", reposition, true);
    document.removeEventListener("keydown", onKey, true);
    if (els) {
      els.backdrop.classList.remove("in");
      const nodes = [els.backdrop, els.hi, els.tip];
      setTimeout(() => nodes.forEach((e) => e && e.remove()), 280);
      els = null;
    }
    try { localStorage.setItem(SEEN_KEY, "1"); } catch (e) { /* ignore */ }
  }

  function onKey(e) {
    if (e.key === "Escape") { e.preventDefault(); end(); }
    else if (e.key === "ArrowRight" || e.key === "Enter") { e.preventDefault(); go(i + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(i - 1); }
  }

  window.PLTour = { start, end };
  function boot() {
    const btn = document.getElementById("tutorialButton");
    if (btn) btn.addEventListener("click", (e) => { e.preventDefault(); start(); });
    let seen = false;
    try { seen = localStorage.getItem(SEEN_KEY) === "1"; } catch (e) { /* ignore */ }
    if (!seen) setTimeout(start, 1400);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();

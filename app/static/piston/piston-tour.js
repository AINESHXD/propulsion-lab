/* PistonLab guided tour — dependency-free, same mechanics as the PropulsionLab
 * tour but in PistonLab's orange and pointed at the crank-angle console.
 *
 * The card is pinned bottom-centre so it can never land in a corner, the window
 * itself is scrolled (never an inner overflow container), and the ring is drawn
 * around the target once it is centred.
 *
 * One difference from the PropulsionLab tour: PistonLab hides whole cards
 * behind the Enthusiast/Engineer toggle (`body.mode-enthusiast .engineer-only`).
 * Rather than flipping the user's mode out from under them, the step list is
 * filtered to what is actually on screen when the tour starts, and a dedicated
 * step explains what the other mode adds. So the tour is honest in either mode
 * and never rings an invisible element. */
(function () {
  "use strict";

  const SEEN_KEY = "plab_tour_seen_v1";

  const ALL_STEPS = [
    { center: true, title: "Welcome to PistonLab",
      body: "This runs real reciprocating-engine cycles, crank angle by crank angle — petrol and diesel, every loss modelled. Quick tour? You can skip whenever." },
    { sel: "#engineType", title: "Petrol or diesel",
      body: "The difference is what starts the fire: a spark in premixed fuel and air, or air compressed hard enough that injected fuel lights itself. Everything downstream follows from that." },
    { sel: "#presetRow", title: "Start from something real-ish",
      body: "Load a representative engine and change whatever you like. These are plausible configurations, not manufacturer data." },
    { sel: "#openBuilder", title: "Or build your own",
      body: "A step-by-step builder: cylinder count and layout, bank angle, crank type, capacity, cam profile, head and boost. It works out firing order and engine balance from the geometry you choose." },
    { sel: "#geometryCard", title: "Bore, stroke, compression",
      body: "Set the physical engine. Bore and stroke give you swept volume; compression ratio sets how hard the charge is squeezed — and on petrol, how close you are to knock." },
    { sel: "#operatingCard", title: "The operating point",
      body: "Speed, throttle and spark or injection timing. Every control here re-solves the whole cycle, so nothing on screen is ever stale." },
    { sel: "#combustionCard", title: "Combustion and losses",
      body: "Wiebe burn duration, wall heat, friction and breathing. Open it if you want to drive the loss models directly instead of accepting the defaults." },
    { sel: "#engineCanvas", title: "Watch it run",
      body: "The piston, valves and flame front are drawn from the same integration that produces the numbers — not a loop of canned animation. Pause it any time." },
    { sel: "#metricCards", title: "The headline numbers",
      body: "Power, torque, BMEP, thermal and volumetric efficiency. What the engine actually does at this operating point." },
    { sel: "#diagramsCard", title: "The loops",
      body: "A real rounded P–V loop — finite burn rate, heat loss and pumping all visible — plus the T–s view. The area inside the loop is the work." },
    { sel: "#breakdownRows", title: "Indicated → brake",
      body: "Where the work goes between the gas pushing on the piston and the power that reaches the crank: pumping first, then friction." },
    { sel: "#energyBar", title: "Where the fuel went",
      body: "Of the energy released, how much became work, how much went out the exhaust, and how much left through the cylinder walls. It sums to one hundred percent because it's a real balance." },
    { sel: "#analysisRows", title: "Crank-resolved detail",
      body: "Peak pressure and where it lands, burned and unburned zone temperatures, end-gas knock margin, and the state at each key crank angle." },
    { sel: "#dynoCanvas", title: "Sweep it",
      body: "Sweep speed and draw torque and power against rpm — the curve you would actually get on a dyno, solved point by point." },
    { sel: "#modeToggle", title: "Two depths",
      body: "Enthusiast keeps it to the essentials. Engineer adds the valve-timing controls, the indicated-to-brake split, the energy balance and the crank-resolved analysis." },
    { center: true, title: "That's the tour",
      body: "Replay it any time from Tutorial up top. Go build an engine." },
  ];

  let steps = ALL_STEPS, i = 0, active = false, els = null;

  // A step earns its place only if its target is actually on screen. Mode
  // gating (and the odd collapsed panel) can hide whole cards; ringing one of
  // those would put a highlight around nothing.
  function visible(sel) {
    const el = document.querySelector(sel);
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 || r.height > 0;
  }

  function injectStyles() {
    if (document.getElementById("plabTourStyles")) return;
    const css = `
      #plabTourBackdrop{position:fixed;inset:0;z-index:9000;background:rgba(8,7,6,.74);
        opacity:0;transition:opacity .25s ease;pointer-events:auto;}
      #plabTourBackdrop.in{opacity:1;}
      #plabTourBackdrop.clear{background:transparent;}
      #plabTourHi{position:fixed;z-index:9001;border-radius:14px;pointer-events:none;opacity:0;
        box-shadow:0 0 0 9999px rgba(8,7,6,.74),0 0 0 1.5px rgba(232,146,62,.95),0 0 30px rgba(232,146,62,.45);
        transition:opacity .2s ease;}
      #plabTourHi.show{opacity:1;}
      #plabTourTip{position:fixed;z-index:9002;left:50%;bottom:30px;transform:translateX(-50%) translateY(8px);
        width:400px;max-width:calc(100vw - 28px);
        background:linear-gradient(180deg,rgba(26,23,20,.98),rgba(16,14,12,.99));
        border:1px solid rgba(255,255,255,.13);border-radius:16px;padding:18px 20px 15px;
        box-shadow:0 24px 60px rgba(0,0,0,.6);backdrop-filter:blur(16px);color:#f4f2ef;
        opacity:0;transition:opacity .2s ease,transform .2s ease;
        font:14px/1.55 -apple-system,BlinkMacSystemFont,"Inter",system-ui,sans-serif;}
      #plabTourTip.show{opacity:1;transform:translateX(-50%) translateY(0);}
      #plabTourTip .eyebrow{font:600 .6rem/1 ui-monospace,monospace;letter-spacing:.18em;
        text-transform:uppercase;color:#e8923e;margin:0 0 9px;}
      #plabTourTip h3{margin:0 0 7px;font-size:1.04rem;font-weight:650;letter-spacing:-.01em;}
      #plabTourTip p{margin:0 0 16px;color:#c9c3bb;font-size:.88rem;}
      #plabTourTip .foot{display:flex;align-items:center;gap:12px;}
      #plabTourTip .prog{flex:1;height:3px;border-radius:3px;background:rgba(255,255,255,.12);overflow:hidden;}
      #plabTourTip .prog i{display:block;height:100%;background:#e8923e;border-radius:3px;
        transition:width .3s cubic-bezier(.4,0,.2,1);}
      #plabTourTip .acts{display:flex;gap:7px;align-items:center;}
      #plabTourTip button{font:inherit;font-size:.8rem;border-radius:10px;padding:7px 13px;cursor:pointer;
        border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.04);color:#f4f2ef;
        transition:border-color .15s,color .15s,background .15s;}
      #plabTourTip button:hover{border-color:#e8923e;color:#fff;background:rgba(232,146,62,.14);}
      #plabTourTip button.primary{background:#e8923e;border-color:#e8923e;color:#141210;font-weight:600;}
      #plabTourTip button.primary:hover{background:#f2ab63;}
      #plabTourTip button.skip{background:none;border:none;color:#8d857b;padding:7px 6px;}
      #plabTourTip button.skip:hover{color:#f4f2ef;}
      @media(prefers-reduced-motion:reduce){
        #plabTourHi,#plabTourTip,#plabTourBackdrop,#plabTourTip .prog i{transition:none;}}
    `;
    const s = document.createElement("style");
    s.id = "plabTourStyles"; s.textContent = css; document.head.appendChild(s);
  }

  function buildDom() {
    const backdrop = document.createElement("div"); backdrop.id = "plabTourBackdrop";
    const hi = document.createElement("div"); hi.id = "plabTourHi";
    const tip = document.createElement("div"); tip.id = "plabTourTip";
    tip.innerHTML =
      `<p class="eyebrow" data-e></p><h3 data-t></h3><p data-b></p>` +
      `<div class="foot"><div class="prog"><i data-p></i></div>` +
      `<div class="acts"><button class="skip" data-skip>Skip</button>` +
      `<button data-back>Back</button><button class="primary" data-next>Next</button></div></div>`;
    document.body.append(backdrop, hi, tip);
    requestAnimationFrame(() => { backdrop.classList.add("in"); tip.classList.add("show"); });
    tip.querySelector("[data-skip]").addEventListener("click", end);
    tip.querySelector("[data-back]").addEventListener("click", () => go(i - 1));
    tip.querySelector("[data-next]").addEventListener("click", () => go(i + 1));
    return { backdrop, hi, tip };
  }

  // Scroll the window, not an inner container, so nothing swallows the scroll.
  function centreInView(el) {
    const r = el.getBoundingClientRect();
    const absTop = r.top + window.scrollY;
    const top = absTop - window.innerHeight / 2 + r.height / 2;
    window.scrollTo({ top: Math.max(0, top), behavior: "auto" });
  }

  function ring(target) {
    const r = target.getBoundingClientRect(), pad = 6;
    els.hi.style.top = `${r.top - pad}px`; els.hi.style.left = `${r.left - pad}px`;
    els.hi.style.width = `${r.width + pad * 2}px`; els.hi.style.height = `${r.height + pad * 2}px`;
  }

  function place(step) {
    const { hi, tip, backdrop } = els;
    tip.querySelector("[data-e]").textContent =
      step.center ? "PistonLab" : `Step ${i} of ${steps.length - 2}`;
    tip.querySelector("[data-t]").textContent = step.title;
    tip.querySelector("[data-b]").textContent = step.body;
    tip.querySelector("[data-p]").style.width = `${(i / (steps.length - 1)) * 100}%`;
    tip.querySelector("[data-back]").style.visibility = i === 0 ? "hidden" : "visible";
    tip.querySelector("[data-next]").textContent = i === steps.length - 1 ? "Done" : "Next";

    const target = step.center ? null : document.querySelector(step.sel);
    const r0 = target && target.getBoundingClientRect();
    if (!target || !r0 || (r0.width === 0 && r0.height === 0)) {
      hi.classList.remove("show");
      backdrop.classList.remove("clear");
      return;
    }
    centreInView(target);
    ring(target);
    backdrop.classList.add("clear");   // the ring's box-shadow does the dimming
    hi.classList.add("show");
  }

  function go(n) {
    if (n < 0) return;
    if (n >= steps.length) return end();
    i = n;
    place(steps[i]);
  }

  function reposition() {
    if (!active) return;
    const step = steps[i];
    if (step.center) return;
    const target = document.querySelector(step.sel);
    if (target) ring(target);
  }

  function start() {
    if (active) return;
    // end() defers its cleanup by 240ms for the fade. Replaying inside that
    // window would leave the outgoing card in the DOM, and querySelector would
    // keep finding *it* instead of the new one — the tour would look stuck on
    // whatever step it closed on. Clear any leftovers before building.
    document.querySelectorAll("#plabTourBackdrop,#plabTourHi,#plabTourTip")
      .forEach((n) => n.remove());
    // Close the builder overlay if it is open — it sits above everything and
    // would bury every ring the tour draws.
    const overlay = document.getElementById("builderOverlay");
    if (overlay && !overlay.hasAttribute("hidden")) {
      const close = document.getElementById("bdClose");
      if (close) close.click();
    }
    steps = ALL_STEPS.filter((s) => s.center || visible(s.sel));
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
      els.tip.classList.remove("show");
      const nodes = [els.backdrop, els.hi, els.tip];
      setTimeout(() => nodes.forEach((e) => e && e.remove()), 240);
      els = null;
    }
    try { localStorage.setItem(SEEN_KEY, "1"); } catch (e) { /* ignore */ }
  }

  function onKey(e) {
    if (e.key === "Escape") { e.preventDefault(); end(); }
    else if (e.key === "ArrowRight" || e.key === "Enter") { e.preventDefault(); go(i + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(i - 1); }
  }

  window.PistonTour = { start, end };

  function boot() {
    const btn = document.getElementById("tutorialButton");
    if (btn) btn.addEventListener("click", (e) => { e.preventDefault(); start(); });
    let seen = false;
    try { seen = localStorage.getItem(SEEN_KEY) === "1"; } catch (e) { /* ignore */ }
    // Wait for the boot screen and the first solve, or the tour rings empty cards.
    if (!seen) setTimeout(start, 2200);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();

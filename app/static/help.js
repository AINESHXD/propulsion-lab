/* PropulsionLab per-feature help.
 *
 * Drops an "ⓘ" button into each analysis tab's heading. Clicking it opens a
 * modal explaining what the feature does, how to use it, and where it matters in
 * real engineering. Dependency-free; injects its own styles + DOM. */
(function () {
  "use strict";

  // Keyed by data-tab-panel. Each: what it does, how to use (steps), where it's used.
  const HELP = {
    graphs: {
      title: "Graphs & reports",
      what: "Everything from your latest run, drawn out — the cycle on T–s and P–v diagrams, temperature and pressure at each station, your sweep results, and the thrust and efficiency breakdown. The buttons here also export a PDF report or a runnable Python script.",
      howto: [
        "Run a cycle on the Cycle tab first — these charts read that result.",
        "Open this tab to see the diagrams.",
        "Use Download PDF for a shareable report, or Export Python to get the exact run as a script you can rerun.",
      ],
      where: "T–s and P–v diagrams are how the cycle gets taught and checked — area on the chart is work and heat. They're the quickest way to see where pressure or efficiency is being lost.",
    },
    compare: {
      title: "Engine compare",
      what: "Runs several engine families at the same flight condition and lines the results up side by side, so you can see which architecture wins where.",
      howto: [
        "Tick the engines you want in the comparison.",
        "Set the shared flight condition.",
        "Press Run compare and read the bars — thrust, TSFC and efficiency for each.",
      ],
      where: "This is the first question on any engine project: which architecture? A turbofan sips fuel at airliner cruise; a turbojet or ramjet takes over once you're supersonic. Compare shows that trade-off directly instead of arguing about it.",
    },
    offdesign: {
      title: "Off-design matching",
      what: "Your design point is just one operating condition. A real engine has fixed hardware and still has to work everywhere else — idle, climb, cruise. This takes that same fixed engine and finds the self-consistent operating point at each throttle setting.",
      howto: [
        "Pick the engine and fix the altitude and Mach.",
        "Press Compute envelope to match the operating line.",
        "Drag the throttle slider to scrub thrust and TSFC up and down the line.",
      ],
      where: "Engines spend almost all their life off-design. Throttle response, part-power fuel burn, and the running line you see on a compressor map all come from matching like this. It's how you check an engine idles cleanly and spools up without stalling.",
    },
    mission: {
      title: "Mission profile",
      what: "Strings off-design points together into a whole flight — climb, cruise, descent — and adds up fuel and time across the trip instead of at a single point.",
      howto: [
        "Build the leg table: altitude, Mach, throttle, and how long each leg lasts.",
        "Press Fly mission.",
        "Read the total fuel and time, plus the per-leg breakdown.",
      ],
      where: "This is how range, endurance and fuel load get decided. Two engines can look the same at cruise but burn very differently over a real mission — flying the profile is how you tell them apart.",
    },
    compressormap: {
      title: "Compressor map",
      what: "The compressor's character: pressure ratio against corrected mass flow, with constant-speed lines, the surge and choke limits, and the matched running line drawn on top.",
      howto: [
        "The map is sized from your Cycle-tab deck — change the deck and recompute to resize it.",
        "Drag the throttle to move the operating point along the running line.",
        "Keep an eye on the surge margin as you throttle back.",
      ],
      where: "This is the central chart of turbomachinery matching. Surge margin is a safety limit — get too close and the compressor stalls. Efficiency and the operating point at every power setting are read straight off this map.",
    },
    optimize: {
      title: "Design optimization · NSGA-II",
      what: "A genetic algorithm searches the design space for the best balance between goals that fight each other — low fuel burn versus high thrust per unit of airflow — while staying inside limits like the turbine-temperature cap.",
      howto: [
        "Set the variable bounds and the constraints.",
        "Press Run optimization and let it evolve.",
        "Read the Pareto front: each dot is a design where you can't improve one goal without giving up another. Colour shows turbine temperature.",
      ],
      where: "There's never a single best engine, only trade-offs. The Pareto front is the menu of optimal compromises — designers pick a point on it based on what the aircraft actually needs.",
    },
  };

  function injectStyles() {
    if (document.getElementById("helpStyles")) return;
    const css = `
      .help-i{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;
        margin-left:10px;border-radius:50%;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.04);
        color:#9197a1;font:600 12px/1 ui-monospace,monospace;cursor:pointer;vertical-align:middle;
        transition:border-color .15s,color .15s,background .15s;}
      .help-i:hover{border-color:#7ba7eb;color:#cfe0ff;background:rgba(123,167,235,.14);}
      #helpBackdrop{position:fixed;inset:0;z-index:9500;background:rgba(7,8,11,.6);backdrop-filter:blur(3px);
        display:none;opacity:0;transition:opacity .2s ease;}
      #helpBackdrop.in{opacity:1;}
      #helpModal{position:fixed;z-index:9501;left:50%;top:50%;transform:translate(-50%,-46%);
        width:520px;max-width:calc(100vw - 28px);max-height:calc(100vh - 80px);overflow:auto;
        background:linear-gradient(180deg,rgba(22,24,30,.99),rgba(15,17,21,.99));
        border:1px solid rgba(255,255,255,.13);border-radius:18px;padding:24px 26px;
        box-shadow:0 30px 80px rgba(0,0,0,.6);color:#f3f4f6;display:none;opacity:0;
        transition:opacity .2s ease,transform .2s ease;
        font:14px/1.6 -apple-system,BlinkMacSystemFont,"Inter",system-ui,sans-serif;}
      #helpModal.in{display:block;opacity:1;transform:translate(-50%,-50%);}
      #helpModal .x{position:absolute;top:16px;right:18px;width:28px;height:28px;border-radius:8px;
        border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.04);color:#c2c7cf;cursor:pointer;
        font-size:13px;line-height:1;padding:0;display:flex;align-items:center;justify-content:center;}
      #helpModal .x:hover{color:#fff;border-color:#7ba7eb;}
      #helpModal h3{margin:0 0 4px;font-size:1.22rem;font-weight:650;letter-spacing:-.01em;padding-right:34px;}
      #helpModal .sec{margin-top:18px;}
      #helpModal .lbl{font:600 .62rem/1 ui-monospace,monospace;letter-spacing:.16em;text-transform:uppercase;color:#7ba7eb;margin:0 0 7px;}
      #helpModal p{margin:0;color:#c8ccd3;font-size:.9rem;}
      #helpModal ol{margin:0;padding-left:20px;color:#c8ccd3;font-size:.9rem;}
      #helpModal ol li{margin:0 0 6px;}
      #helpModal .where{border-left:2px solid rgba(123,167,235,.5);padding-left:13px;color:#aeb4bd;font-size:.88rem;}
      @media(prefers-reduced-motion:reduce){#helpBackdrop,#helpModal{transition:none;}}
    `;
    const s = document.createElement("style");
    s.id = "helpStyles"; s.textContent = css; document.head.appendChild(s);
  }

  let backdrop, modal;

  function buildModal() {
    backdrop = document.createElement("div"); backdrop.id = "helpBackdrop";
    modal = document.createElement("div"); modal.id = "helpModal";
    document.body.append(backdrop, modal);
    backdrop.addEventListener("click", close);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  }

  function open(key) {
    const h = HELP[key]; if (!h) return;
    const steps = h.howto.map((s) => `<li>${s}</li>`).join("");
    modal.innerHTML =
      `<button class="x" aria-label="Close">✕</button>` +
      `<h3>${h.title}</h3>` +
      `<div class="sec"><p class="lbl">What it does</p><p>${h.what}</p></div>` +
      `<div class="sec"><p class="lbl">How to use it</p><ol>${steps}</ol></div>` +
      `<div class="sec"><p class="lbl">Where it's used</p><p class="where">${h.where}</p></div>`;
    modal.querySelector(".x").addEventListener("click", close);
    backdrop.style.display = "block"; modal.style.display = "block";
    requestAnimationFrame(() => { backdrop.classList.add("in"); modal.classList.add("in"); });
  }

  function close() {
    if (!modal) return;
    backdrop.classList.remove("in"); modal.classList.remove("in");
    setTimeout(() => { backdrop.style.display = "none"; modal.style.display = "none"; }, 200);
  }

  function boot() {
    injectStyles();
    buildModal();
    Object.keys(HELP).forEach((key) => {
      const panel = document.querySelector(`[data-tab-panel="${key}"]`);
      if (!panel) return;
      const heading = panel.querySelector(".panel-heading h2") || panel.querySelector(".panel-heading");
      if (!heading || heading.querySelector(".help-i")) return;
      const btn = document.createElement("button");
      btn.className = "help-i"; btn.type = "button"; btn.textContent = "i";
      btn.title = `How to use: ${HELP[key].title}`;
      btn.setAttribute("aria-label", `How to use ${HELP[key].title}`);
      btn.addEventListener("click", () => open(key));
      heading.appendChild(btn);
    });
  }

  window.PLHelp = { open, close };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();

/* ============================================================================
 * PropulsionLab — Engine case studies tab
 * ----------------------------------------------------------------------------
 * Ten production gas-turbine engines with public-estimated specifications and
 * a technical overview of each one's architecture and cycle. No third-party /
 * copyrighted imagery is used.
 *
 * All figures are approximate, public-estimated, and given for a representative
 * variant — exact numbers vary by sub-model and rating. Self-contained IIFE;
 * relies only on the generic data-tab / data-tab-panel switching in app.js.
 * ========================================================================== */
(function () {
  "use strict";

  /* ---- Engine dataset -------------------------------------------------- */
  const ENGINES = [
    {
      id: "jt8d",
      name: "Pratt & Whitney JT8D",
      maker: "Pratt & Whitney",
      family: "Low-bypass turbofan",
      eis: "1964",
      bypass: "≈ 1.0 – 1.7",
      opr: "≈ 16 – 21",
      thrust: "62 – 96 kN",
      fan: "≈ 1.0 m",
      spoolsText: "2-spool",
      apps: "Boeing 727, 737-100/-200 · DC-9 · MD-80",
      tech: [
        "A two-spool low-bypass turbofan derived from the J52 turbojet. A " +
          "two-stage front fan pressurises a bypass duct with a bypass ratio " +
          "near unity, so the hot core jet still produces most of the thrust. " +
          "Core and bypass streams mix in a long common cowl ahead of a single " +
          "convergent nozzle, rather than exhausting separately as on later " +
          "high-bypass engines.",
        "By modern standards the overall pressure ratio (≈ 16–21) and turbine " +
          "temperatures are low, which means high specific fuel consumption and " +
          "a loud jet — the later -200 'refan' and external hush-kits chased " +
          "tightening noise rules. Its lasting significance is volume and " +
          "ruggedness: it was the workhorse that made the first generation of " +
          "short/medium-haul jetliners economic.",
      ],
    },
    {
      id: "cf6",
      name: "GE CF6",
      maker: "General Electric",
      family: "High-bypass turbofan",
      eis: "1971",
      bypass: "≈ 4.3 – 5.3",
      opr: "≈ 28 – 32",
      thrust: "180 – 274 kN",
      fan: "≈ 2.2 – 2.7 m",
      spoolsText: "2-spool",
      apps: "Boeing 747, 767 · A300/A310 · DC-10, MD-11",
      tech: [
        "GE's first big commercial high-bypass turbofan, scaled down from the " +
          "TF39 that powered the C-5 Galaxy. The two-spool layout puts a single " +
          "large fan plus a few booster stages on the LP shaft and a " +
          "high-pressure-ratio compressor, annular combustor and air-cooled HP " +
          "turbine on the HP shaft.",
        "A bypass ratio of roughly 4–5 lifts propulsive efficiency far above " +
          "the JT8D generation, which is why it defined the early wide-body " +
          "twin and quad market. Just as important, its core became a " +
          "technology lineage: the CF6-80 series, and ultimately the GE90 and " +
          "GEnx, all trace back to this architecture.",
      ],
    },
    {
      id: "v2500",
      name: "IAE V2500",
      maker: "International Aero Engines",
      family: "High-bypass turbofan",
      eis: "1989",
      bypass: "≈ 4.6",
      opr: "≈ 33",
      thrust: "98 – 147 kN",
      fan: "≈ 1.6 m",
      spoolsText: "2-spool",
      apps: "A320 family · MD-90",
      tech: [
        "A two-spool high-bypass turbofan built by a five-nation consortium " +
          "(Pratt & Whitney, Rolls-Royce, Japanese Aero Engines and German/" +
          "Italian partners). It pairs a wide-chord fan with a notably " +
          "high-pressure-ratio HP compressor, giving a clean, efficient core " +
          "for its thrust class.",
        "On the A320 it is the direct rival to the CFM56, and the two engines " +
          "split the single-aisle market for two decades. The V2500 earned a " +
          "reputation for low fuel burn and long on-wing life, and its core " +
          "later seeded Pratt & Whitney's thinking ahead of the geared fan.",
      ],
    },
    {
      id: "cfm56",
      name: "CFM56-5B / -7B",
      maker: "CFM International (GE + Safran)",
      family: "High-bypass turbofan",
      eis: "1996",
      bypass: "≈ 5.0 – 5.5",
      opr: "≈ 32 – 38",
      thrust: "97 – 142 kN",
      fan: "≈ 1.55 – 1.73 m",
      spoolsText: "2-spool",
      apps: "A320 family · Boeing 737 Classic/NG",
      tech: [
        "The best-selling jet engine in history. A two-spool design that grafts " +
          "GE's F101 core (developed for the B-1 bomber) onto a Snecma " +
          "low-pressure system: single fan, booster stages, a nine-stage HP " +
          "compressor, an annular combustor — single-annular, or dual-annular " +
          "on low-NOₓ variants — and cooled HP/LP turbines.",
        "Bypass ratio around 5 and a steadily climbing pressure ratio across " +
          "the -5B/-7B variants made it the default narrowbody powerplant for " +
          "three decades. Its commercial importance is hard to overstate: tens " +
          "of thousands built, and the proving ground for the CFM partnership " +
          "that went on to produce the LEAP.",
      ],
    },
    {
      id: "pw4000",
      name: "Pratt & Whitney PW4000",
      maker: "Pratt & Whitney",
      family: "High-bypass turbofan",
      eis: "1987",
      bypass: "≈ 5.0 – 6.4",
      opr: "≈ 27 – 35",
      thrust: "222 – 436 kN",
      fan: "94 / 100 / 112 in",
      spoolsText: "2-spool",
      apps: "747-400 · 767 · 777 · A300/A310 · A330 · MD-11",
      tech: [
        "A two-spool high-bypass family built around one core philosophy but " +
          "offered in three fan diameters — 94, 100 and 112 inches — to span " +
          "everything from the A310 to the 777. Full-authority digital engine " +
          "control (FADEC) was standard, and the larger members raised bypass " +
          "ratio toward 6 for better cruise efficiency.",
        "The 112-inch variant was among the largest fans of the early 1990s and " +
          "powered the first 777s, putting Pratt & Whitney head-to-head with " +
          "the GE90 and Trent 800 in the big-twin market. The family showed how " +
          "far a single core could be stretched across thrust classes.",
      ],
    },
    {
      id: "ge90",
      name: "GE90",
      maker: "General Electric",
      family: "High-bypass turbofan",
      eis: "1995",
      bypass: "≈ 8 – 9",
      opr: "≈ 40 – 42",
      thrust: "330 – 512 kN",
      fan: "≈ 3.12 – 3.25 m",
      spoolsText: "2-spool",
      apps: "Boeing 777",
      tech: [
        "The most powerful turbofan ever certified — the GE90-115B recorded " +
          "roughly 569 kN on test, a Guinness world record. It was the first " +
          "production engine with swept, hollow carbon-fibre composite fan " +
          "blades, allowing a 3.25 m fan (wider than a 737 fuselage) that turns " +
          "a high bypass ratio without an unmanageable blade count.",
        "Behind that fan sits a high-pressure-ratio core derived from GE's " +
          "energy-efficient-engine research, with a high overall pressure ratio " +
          "for strong thermal efficiency. Built specifically to power the 777, " +
          "it demonstrated that a single very large engine could replace the " +
          "three- and four-engine wide-bodies it competed with.",
      ],
    },
    {
      id: "genx",
      name: "GEnx",
      maker: "General Electric",
      family: "High-bypass turbofan",
      eis: "2011",
      bypass: "≈ 8 – 9.6",
      opr: "≈ 43 – 58",
      thrust: "296 – 339 kN",
      fan: "≈ 2.66 – 2.82 m",
      spoolsText: "2-spool",
      apps: "Boeing 787 · 747-8",
      tech: [
        "A direct technology descendant of the GE90, re-sized for the 787 and " +
          "747-8. It uses composite fan blades and — a first for a large engine " +
          "— a composite fan case, cutting weight, while a very high overall " +
          "pressure ratio (toward ~58 with the booster) pushes thermal " +
          "efficiency. The TAPS (Twin-Annular Pre-Swirl) combustor lowers NOₓ.",
        "Chevron (sawtooth) nozzle trailing edges mix the exhaust more gently " +
          "to cut community noise. Together the composites, high OPR and modern " +
          "combustor deliver a large step in fuel burn over the engines it " +
          "replaced on twin-aisle aircraft.",
      ],
    },
    {
      id: "leap",
      name: "CFM LEAP-1A / -1B",
      maker: "CFM International (GE + Safran)",
      family: "High-bypass turbofan",
      eis: "2016",
      bypass: "≈ 9 – 11",
      opr: "≈ 40 – 50",
      thrust: "100 – 156 kN",
      fan: "≈ 1.76 – 1.98 m",
      spoolsText: "2-spool",
      apps: "A320neo · Boeing 737 MAX",
      tech: [
        "The CFM56's successor and a showcase of materials engineering: the fan " +
          "blades are three-dimensionally woven carbon-fibre, made by resin " +
          "transfer moulding, so the fan can grow larger and lighter and raise " +
          "the bypass ratio toward 11. Ceramic-matrix-composite (CMC) shrouds " +
          "in the hot section tolerate higher turbine temperatures than metal.",
        "A Twin-Annular Pre-Swirl combustor and a higher overall pressure ratio " +
          "combine for roughly 15 % lower fuel burn than the CFM56 it replaces, " +
          "with lower NOₓ. It is now the dominant powerplant on the latest " +
          "single-aisle jets, sharing that market with Pratt's geared fan.",
      ],
    },
    {
      id: "gtf",
      name: "P&W GTF (PW1000G)",
      maker: "Pratt & Whitney",
      family: "Geared high-bypass turbofan",
      eis: "2016",
      bypass: "≈ 9 – 12",
      opr: "≈ 40 – 50",
      thrust: "67 – 156 kN",
      fan: "≈ 1.42 – 2.06 m",
      spoolsText: "2-spool + reduction gear",
      apps: "A320neo · A220 · Embraer E-Jets E2",
      tech: [
        "The defining efficiency idea of the 2010s narrowbody generation. A " +
          "planetary reduction gearbox of roughly 3:1 sits between the fan and " +
          "the low-pressure spool, so a large fan can turn slowly — its " +
          "aerodynamic optimum — while the LP compressor and turbine spin fast, " +
          "theirs. Decoupling the two lets each run near its best speed.",
        "Because the LP spool runs fast, it needs far fewer compressor and " +
          "turbine stages, cutting parts and weight, and the slow fan can be " +
          "large for a high bypass ratio and quiet operation. The pay-off is a " +
          "double-digit fuel-burn improvement; the engineering price is a " +
          "heavily loaded gearbox that must shed significant heat reliably.",
      ],
    },
    {
      id: "trentxwb",
      name: "Rolls-Royce Trent XWB",
      maker: "Rolls-Royce",
      family: "Three-spool high-bypass turbofan",
      eis: "2015",
      bypass: "≈ 9.3",
      opr: "≈ 50",
      thrust: "330 – 431 kN",
      fan: "≈ 3.0 m",
      spoolsText: "3-spool",
      apps: "Airbus A350 XWB",
      tech: [
        "Rolls-Royce's signature three-spool architecture: independent low-, " +
          "intermediate- and high-pressure shafts, each free to turn at its own " +
          "optimum speed. Splitting the compression across three spools keeps " +
          "the shafts short and stiff and lets every compressor and turbine " +
          "stage run near its aerodynamic best, at the cost of mechanical " +
          "complexity (three concentric shafts and bearing systems).",
        "With an overall pressure ratio around 50 and a bypass ratio near 9, it " +
          "was the most efficient large civil engine in service at entry, and " +
          "it powers the A350 exclusively. It is the modern flagship of the " +
          "three-spool lineage Rolls-Royce has pursued since the RB211.",
      ],
    },
  ];

  /* ---- Representative turbofan design points --------------------------
   * Each maps the engine onto the simulator's two-spool turbofan inputs at a
   * cruise design point. core_compressor_pressure_ratio is chosen so that
   * fan_pressure_ratio × core HPC ≈ the engine's overall pressure ratio.
   * These are illustrative design points, not certification data — and the
   * simulator models a plain two-spool fan, so the geared (GTF) and three-spool
   * (Trent XWB) architectures are represented by their bypass ratio, fan PR and
   * OPR rather than by an explicit gearbox or third shaft. */
  const SIM = {
    jt8d:     { nozzle_configuration: "mixed",    altitude_m: 9000,  mach: 0.74, total_mass_flow_air_kg_s: 145,  bypass_ratio: 1.0,  fan_pressure_ratio: 1.9,  core_compressor_pressure_ratio: 9,  turbine_inlet_temperature_K: 1150 },
    cf6:      { nozzle_configuration: "separate", altitude_m: 10000, mach: 0.80, total_mass_flow_air_kg_s: 600,  bypass_ratio: 4.8,  fan_pressure_ratio: 1.6,  core_compressor_pressure_ratio: 19, turbine_inlet_temperature_K: 1480 },
    v2500:    { nozzle_configuration: "separate", altitude_m: 10000, mach: 0.78, total_mass_flow_air_kg_s: 355,  bypass_ratio: 4.6,  fan_pressure_ratio: 1.6,  core_compressor_pressure_ratio: 21, turbine_inlet_temperature_K: 1500 },
    cfm56:    { nozzle_configuration: "separate", altitude_m: 10000, mach: 0.78, total_mass_flow_air_kg_s: 350,  bypass_ratio: 5.2,  fan_pressure_ratio: 1.6,  core_compressor_pressure_ratio: 22, turbine_inlet_temperature_K: 1530 },
    pw4000:   { nozzle_configuration: "separate", altitude_m: 10000, mach: 0.80, total_mass_flow_air_kg_s: 800,  bypass_ratio: 5.5,  fan_pressure_ratio: 1.6,  core_compressor_pressure_ratio: 20, turbine_inlet_temperature_K: 1500 },
    ge90:     { nozzle_configuration: "separate", altitude_m: 10500, mach: 0.84, total_mass_flow_air_kg_s: 1350, bypass_ratio: 8.5,  fan_pressure_ratio: 1.55, core_compressor_pressure_ratio: 27, turbine_inlet_temperature_K: 1600 },
    genx:     { nozzle_configuration: "separate", altitude_m: 10500, mach: 0.85, total_mass_flow_air_kg_s: 1100, bypass_ratio: 9.0,  fan_pressure_ratio: 1.5,  core_compressor_pressure_ratio: 33, turbine_inlet_temperature_K: 1600 },
    leap:     { nozzle_configuration: "separate", altitude_m: 10500, mach: 0.78, total_mass_flow_air_kg_s: 360,  bypass_ratio: 10.0, fan_pressure_ratio: 1.5,  core_compressor_pressure_ratio: 30, turbine_inlet_temperature_K: 1600 },
    gtf:      { nozzle_configuration: "separate", altitude_m: 10500, mach: 0.78, total_mass_flow_air_kg_s: 350,  bypass_ratio: 11.0, fan_pressure_ratio: 1.45, core_compressor_pressure_ratio: 31, turbine_inlet_temperature_K: 1600 },
    trentxwb: { nozzle_configuration: "separate", altitude_m: 10500, mach: 0.85, total_mass_flow_air_kg_s: 1350, bypass_ratio: 9.3,  fan_pressure_ratio: 1.5,  core_compressor_pressure_ratio: 33, turbine_inlet_temperature_K: 1650 },
  };

  /* ---- Rendering ------------------------------------------------------- */
  function specRow(label, value) {
    return `<div class="cs-spec"><dt>${label}</dt><dd>${value}</dd></div>`;
  }

  // Engines with a published long-form case-study page (build_case_studies.py).
  // All ten engines now have a page (Day 28); see /lab/case-studies/ for the index.
  const LONGFORM_IDS = new Set([
    "jt8d", "cf6", "pw4000", "v2500", "cfm56",
    "ge90", "genx", "leap", "gtf", "trentxwb",
  ]);

  function detailHTML(eng) {
    const paras = eng.tech.map((p) => `<p>${p}</p>`).join("");
    const fullPage = LONGFORM_IDS.has(eng.id)
      ? `<a class="cs-fullpage-link" href="/lab/case-studies/${eng.id}.html">` +
        `Read the full case study →</a>`
      : "";
    return (
      `<div class="cs-detail-body">` +
      `<p class="cs-eyebrow">${eng.maker}</p>` +
      `<h3 class="cs-detail-title">${eng.name}</h3>` +
      `<p class="cs-family">${eng.family} · ${eng.spoolsText} · entered service ${eng.eis}</p>` +
      `<dl class="cs-specs">` +
      specRow("Bypass ratio", eng.bypass) +
      specRow("Overall PR", eng.opr) +
      specRow("Max thrust", eng.thrust) +
      specRow("Fan diameter", eng.fan) +
      `</dl>` +
      `<p class="cs-apps"><span>Applications</span>${eng.apps}</p>` +
      `<div class="cs-tech"><p class="cs-tech-label">Technical overview</p>${paras}</div>` +
      fullPage +
      `<button type="button" class="ghost-button cs-sim-link" data-engine="${eng.id}">` +
      `Load this engine in the turbofan simulator →</button>` +
      `<p class="cs-sim-note">Loads a representative cruise design point and runs ` +
      `the two-spool turbofan cycle. Illustrative, not certification data.</p>` +
      `</div>`
    );
  }

  let initialised = false;
  function init() {
    if (initialised) return;
    const rail = document.getElementById("caseStudyRail");
    const detail = document.getElementById("caseStudyDetail");
    if (!rail || !detail) return;
    initialised = true;

    rail.innerHTML = ENGINES.map(
      (e, i) =>
        `<button type="button" class="cs-rail-item${i === 0 ? " active" : ""}" ` +
        `data-engine="${e.id}"><span class="cs-rail-name">${e.name}</span>` +
        `<span class="cs-rail-sub"><span class="cs-yr">${e.eis}</span>` +
        `<span class="cs-bpr">BPR ${e.bypass}</span></span></button>`,
    ).join("");

    function select(id) {
      const eng = ENGINES.find((e) => e.id === id) || ENGINES[0];
      detail.innerHTML = detailHTML(eng);
      rail.querySelectorAll(".cs-rail-item").forEach((b) => {
        b.classList.toggle("active", b.dataset.engine === eng.id);
      });
    }

    rail.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".cs-rail-item");
      if (btn) select(btn.dataset.engine);
    });

    detail.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".cs-sim-link");
      if (!btn) return;
      const sim = SIM[btn.dataset.engine];
      if (typeof window.loadEngineCaseStudy === "function" && sim) {
        window.loadEngineCaseStudy("turbofan", sim);
      } else if (typeof window.activateConsoleTab === "function") {
        // Fallback: at least switch to the Cycle tab.
        window.activateConsoleTab("dashboard");
        document
          .querySelector(".console-tabs")
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });

    select(ENGINES[0].id);
  }

  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest('.tab-button[data-tab="casestudies"]');
    if (btn) init();
  });
  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);

  window.__initCaseStudies = init;
})();

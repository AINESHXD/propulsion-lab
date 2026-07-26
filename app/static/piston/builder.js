/* =============================================================
   DAS LABS · PistonLab — custom engine builder

   A branching wizard over the crank-angle solver. The flow is a
   declarative graph, not a fixed list: every node carries a
   `when(answers)` predicate, so the path you walk depends on what
   you have already chosen. Pick a V and you get asked for a bank
   angle, a crank plane and — only if your bank angle leaves the
   engine odd-fire — a split-crankpin offset. Pick an inline and
   none of those exist. Pick compression ignition and the fuel,
   compression-ratio range and cam defaults all move with it.

   Live readouts inside a step are previews computed from the same
   closed-form relations the solver uses (720/n for firing, the
   cube-root capacity solve). The authoritative numbers — balance,
   breathing, effective compression ratio — come back from the
   Python solver on the review step and on build.
   ============================================================= */

const API_SIM = "/piston/simulate";

/* ---------- small helpers ---------- */
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (v, d = 1) => (v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(d));
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Even-fire interval for a four-stroke: n firings per 720 deg. */
const idealInterval = (a) => (360 * (a.strokes_per_cycle / 2)) / a.cylinders;

/** Does a shared-crankpin V fire evenly? Only when the bank separation
 *  (bank angle plus any split-pin offset) equals the ideal interval. */
const isEvenFire = (a) => {
  if (a.layout_kind !== "vee" && a.layout_kind !== "w") return true;
  const sep = (a.bank_angle_deg || 0) + (a.crankpin_offset_deg || 0);
  return Math.abs(sep - idealInterval(a)) < 0.5;
};

/** Bore and stroke from a capacity and a bore/stroke ratio (preview only —
 *  the solver returns the authoritative pair). */
const boreStroke = (a) => {
  const v = (a.displacement_L || 2) * 1e-3;
  const k = a.bore_stroke_ratio || 1;
  const bore = Math.cbrt((4 * k * v) / (a.cylinders * Math.PI));
  return { bore, stroke: bore / k };
};

/* Cylinder counts a given arrangement can actually be built in. */
const CYLINDER_CHOICES = {
  single: [1],
  inline: [2, 3, 4, 5, 6, 8],
  vee: [2, 4, 6, 8, 10, 12, 16],
  flat: [2, 4, 6, 8, 12],
  w: [8, 12, 16],
  radial: [3, 5, 7, 9],
};

/* Cam presets. Each is a full valve-event set, so picking one is a real
   choice about where the engine makes its power, not a slider nudge. */
const CAM_PRESETS = {
  economy: { label: "Economy", sub: "short duration, small overlap",
    ivo: 6, ivc: 34, evo: 40, evc: 6,
    note: "Closes the intake early: strong low-end filling and a high effective compression ratio." },
  street: { label: "Street", sub: "the default road cam",
    ivo: 10, ivc: 45, evo: 48, evc: 10,
    note: "A balanced road cam. Modest overlap keeps idle clean." },
  sport: { label: "Sport", sub: "longer duration, more overlap",
    ivo: 20, ivc: 60, evo: 62, evc: 20,
    note: "Trades bottom-end for top-end: later intake close fills better once the ports are flowing hard." },
  race: { label: "Race", sub: "big duration and overlap",
    ivo: 34, ivc: 80, evo: 78, evc: 34,
    note: "Only works at speed. Huge overlap scavenges at high rpm and is useless below it." },
  miller: { label: "Miller / Atkinson", sub: "very late intake close",
    ivo: 4, ivc: 100, evo: 45, evc: 8,
    note: "Deliberately spills charge back out so the engine expands further than it compresses — efficiency over power." },
};

/* Head presets: valve count drives the sizing, because four small valves
   out-flow two big ones for the same bore. */
const HEAD_PRESETS = {
  two: { label: "2-valve", sub: "one in, one out", niv: 1, nev: 1, div: 0.45, dev: 0.39,
    note: "Simple and cheap. One big valve per side, but curtain area runs out early." },
  four: { label: "4-valve", sub: "two in, two out", niv: 2, nev: 2, div: 0.38, dev: 0.33,
    note: "The modern default. More curtain area for the same bore, so it breathes much further up the rev range." },
  five: { label: "5-valve", sub: "three in, two out", niv: 3, nev: 2, div: 0.30, dev: 0.33,
    note: "Maximum intake curtain area. Complex, and the gains over a good 4-valve are small." },
};

const EXHAUST_PRESETS = {
  race: { label: "Open / race", sub: "large bore, no silencing", value: 0.15 },
  sport: { label: "Sport", sub: "free-flowing system", value: 0.7 },
  stock: { label: "Stock", sub: "silenced road system", value: 1.4 },
  restricted: { label: "Restricted", sub: "catalyst and long run", value: 2.6 },
};

/* =============================================================
   THE STEP GRAPH
   Each node: id, eyebrow, title, blurb, controls, optional
   `when(answers)` gate and `note(answers)` live readout.
   ============================================================= */
const STEPS = [
  {
    id: "character",
    eyebrow: "Brief",
    title: "What are you building?",
    blurb: "This only seeds sensible starting points. Every value stays editable further in.",
    controls: [{
      kind: "choice", key: "character", columns: 2,
      options: [
        { value: "road", label: "Road car", sub: "tractable, everyday" },
        { value: "track", label: "Track weapon", sub: "revs and power" },
        { value: "economy", label: "Economy", sub: "efficiency first" },
        { value: "haul", label: "Truck / tow", sub: "low-end torque" },
      ],
    }],
    apply: (a, v) => {
      const seed = {
        road: { rpm: 5000, cam: "street", exhaust: "stock", head: "four", equivalence_ratio: 1.0 },
        track: { rpm: 7500, cam: "race", exhaust: "race", head: "four", equivalence_ratio: 1.05 },
        economy: { rpm: 3000, cam: "economy", exhaust: "stock", head: "four", equivalence_ratio: 0.95 },
        haul: { rpm: 2200, cam: "economy", exhaust: "restricted", head: "four", equivalence_ratio: 0.7 },
      }[v] || {};
      Object.assign(a, seed);
    },
  },

  {
    id: "ignition",
    eyebrow: "Combustion",
    title: "How does the charge light?",
    blurb: "The single decision that shapes everything downstream: fuel, compression, timing and how it is fuelled.",
    controls: [{
      kind: "choice", key: "ignition", columns: 2,
      options: [
        { value: "spark", label: "Spark ignition", sub: "petrol · premixed",
          desc: "Fuel and air are mixed before compression, so compression is capped by knock." },
        { value: "compression", label: "Compression ignition", sub: "diesel · injected",
          desc: "Air alone is compressed until injected fuel self-ignites. Runs lean at high compression." },
      ],
    }],
    apply: (a, v) => {
      if (v === "compression") {
        Object.assign(a, {
          fuel: "diesel", compression_ratio: 18, combustion_start_deg: -8,
          burn_duration_deg: 65, equivalence_ratio: Math.min(a.equivalence_ratio ?? 0.7, 0.7),
          rpm: Math.min(a.rpm ?? 3000, 4000),
        });
      } else {
        Object.assign(a, {
          fuel: a.fuel && a.fuel !== "diesel" ? a.fuel : "gasoline",
          compression_ratio: 11, combustion_start_deg: -15, burn_duration_deg: 50,
        });
      }
    },
  },

  {
    id: "fuel",
    eyebrow: "Combustion",
    title: "Which fuel?",
    blurb: "Heat release comes from the fuel's own chemistry, so this moves the air-fuel ratio and the knock ceiling.",
    when: (a) => a.ignition === "spark",
    controls: [{
      kind: "choice", key: "fuel", columns: 3,
      options: [
        { value: "gasoline", label: "Gasoline", sub: "RON 95 · AFR 14.7" },
        { value: "ethanol", label: "Ethanol", sub: "RON 108 · AFR 9.0" },
        { value: "methanol", label: "Methanol", sub: "RON 109 · AFR 6.4" },
      ],
    }],
    note: (a) => a.fuel === "gasoline"
      ? "Pump petrol. Knock is the limit on compression and boost."
      : "High octane and a big charge-cooling effect, so it tolerates far more compression and boost than petrol — but burns much richer, so it needs more fuel flow for the same air.",
  },

  {
    id: "layout",
    eyebrow: "Architecture",
    title: "How are the cylinders arranged?",
    blurb: "Arrangement does not change the gas cycle — every cylinder runs the same one — but it decides how the engine shakes, how evenly it fires, and how much friction it carries.",
    controls: [{
      kind: "choice", key: "layout_kind", columns: 3,
      options: [
        { value: "inline", label: "Inline", sub: "one bank" },
        { value: "vee", label: "V", sub: "two banks, shared pins" },
        { value: "flat", label: "Flat / boxer", sub: "opposed, own pins" },
        { value: "single", label: "Single", sub: "one cylinder" },
        { value: "w", label: "W", sub: "four narrow banks" },
        { value: "radial", label: "Radial", sub: "one row, around the crank" },
      ],
    }],
    apply: (a, v) => {
      const allowed = CYLINDER_CHOICES[v] || [4];
      if (!allowed.includes(a.cylinders)) a.cylinders = allowed[Math.min(2, allowed.length - 1)];
      if (v === "vee" || v === "w") {
        a.bank_angle_deg = idealInterval(a);
      } else {
        a.bank_angle_deg = 0;
        a.crankpin_offset_deg = 0;
      }
    },
  },

  {
    id: "cylinders",
    eyebrow: "Architecture",
    title: "How many cylinders?",
    blurb: "Only counts this arrangement can actually be built in are offered.",
    controls: [{
      kind: "choice", key: "cylinders", columns: 4, numeric: true,
      options: (a) => (CYLINDER_CHOICES[a.layout_kind] || [4]).map((n) => ({
        value: n, label: String(n), sub: n === 1 ? "cylinder" : "cylinders",
      })),
    }],
    apply: (a) => {
      if (a.layout_kind === "vee" || a.layout_kind === "w") a.bank_angle_deg = idealInterval(a);
    },
    note: (a) => `A four-stroke fires ${a.cylinders} times per 720° of crank, so even firing means one power stroke every <b>${fmt(idealInterval(a), 0)}°</b>.`,
  },

  {
    id: "bank",
    eyebrow: "Architecture",
    title: "What included angle between the banks?",
    blurb: "Two cylinders sharing a crankpin fire one bank-angle apart. Match the angle to the ideal interval and the engine fires evenly; miss it and it does not.",
    when: (a) => a.layout_kind === "vee" || a.layout_kind === "w",
    controls: [{
      kind: "range", key: "bank_angle_deg", min: 15, max: 180, step: 5, unit: "°",
      label: "Included angle",
    }],
    note: (a) => {
      const ideal = idealInterval(a);
      const even = Math.abs((a.bank_angle_deg || 0) - ideal) < 0.5;
      const sep = a.bank_angle_deg || 0;
      return even
        ? `<b>Even-fire.</b> ${fmt(sep, 0)}° matches the ideal ${fmt(ideal, 0)}° interval exactly.`
        : `<b>Odd-fire.</b> Firing alternates ${fmt(sep, 0)}° / ${fmt(2 * ideal - sep, 0)}° against an ideal of ${fmt(ideal, 0)}°. That lopes at idle — you can leave it, or fix it with a split crankpin on the next step. The even-fire angle here is <b>${fmt(ideal, 0)}°</b>.`;
    },
  },

  {
    id: "splitpin",
    eyebrow: "Architecture",
    title: "Split the crankpin to even it out?",
    blurb: "Offsetting the second bank's crankpin adds to the effective bank separation. It is how an odd-fire V is brought back to even without changing the vee angle.",
    when: (a) => (a.layout_kind === "vee" || a.layout_kind === "w") && !isEvenFire({ ...a, crankpin_offset_deg: 0 }),
    controls: [{
      kind: "range", key: "crankpin_offset_deg", min: -60, max: 60, step: 5, unit: "°",
      label: "Crankpin offset",
    }],
    note: (a) => {
      const need = idealInterval(a) - (a.bank_angle_deg || 0);
      return isEvenFire(a)
        ? "<b>Even-fire.</b> The offset closes the gap exactly."
        : `Still odd-fire. An offset of <b>${fmt(need, 0)}°</b> would even it out. Leaving it at 0° keeps the classic odd-fire character.`;
    },
  },

  {
    id: "crankplane",
    eyebrow: "Architecture",
    title: "Flat-plane or cross-plane crank?",
    blurb: "Where the throws sit around the crank. This is the whole argument between a screaming European V8 and a rumbling American one, and it is a real balance difference, not a sound preference.",
    when: (a) => a.layout_kind === "vee" && a.cylinders % 4 === 0 && a.cylinders >= 8,
    controls: [{
      kind: "choice", key: "crank_type", columns: 2,
      options: [
        { value: "flat_plane", label: "Flat-plane", sub: "throws on 0/180",
          desc: "Light crank, revs freely, but leaves a secondary shaking force." },
        { value: "cross_plane", label: "Cross-plane", sub: "throws on 0/90/270/180",
          desc: "Cancels the secondary shake; needs heavy counterweights and leaves a rocking couple." },
      ],
    }],
  },

  {
    id: "capacity",
    eyebrow: "Geometry",
    title: "How big, and what shape?",
    blurb: "Capacity plus a bore/stroke ratio fixes the bore and the stroke. Oversquare revs; undersquare pulls.",
    controls: [
      { kind: "range", key: "displacement_L", min: 0.1, max: 12, step: 0.1, unit: " L", label: "Total capacity" },
      { kind: "range", key: "bore_stroke_ratio", min: 0.6, max: 1.6, step: 0.01, unit: "", label: "Bore / stroke ratio" },
    ],
    note: (a) => {
      const { bore, stroke } = boreStroke(a);
      const perCyl = (a.displacement_L * 1000) / a.cylinders;
      const meanPS = (2 * stroke * a.rpm) / 60;
      const shape = a.bore_stroke_ratio > 1.05 ? "oversquare — short stroke, happy to rev"
        : a.bore_stroke_ratio < 0.95 ? "undersquare — long stroke, torque biased"
          : "square";
      return `<b>${fmt(bore * 1000, 1)} mm</b> bore × <b>${fmt(stroke * 1000, 1)} mm</b> stroke, ${fmt(perCyl, 0)} cc per cylinder (${shape}).<br />Mean piston speed at ${fmt(a.rpm, 0)} rpm is <b>${fmt(meanPS, 1)} m/s</b>${meanPS > 25 ? " — past what production engines survive." : meanPS > 20 ? " — racing territory." : "."}`;
    },
  },

  {
    id: "compression",
    eyebrow: "Geometry",
    title: "Compression ratio",
    blurb: "The geometric ratio. What the charge actually sees depends on when the intake valve shuts, which comes later.",
    controls: [
      { kind: "range", key: "compression_ratio", min: 6, max: 24, step: 0.1, unit: ":1", label: "Geometric ratio" },
      { kind: "range", key: "rod_ratio", min: 1.5, max: 5, step: 0.05, unit: "", label: "Rod ratio L/a" },
    ],
    note: (a) => {
      const cr = a.compression_ratio;
      const warn = a.ignition === "spark"
        ? (cr > 13 ? "Very high for a spark engine — expect the knock flag unless you are on ethanol or methanol." : cr < 8 ? "Low: this is boost territory." : "A normal spark-ignition range.")
        : (cr < 14 ? "Low for compression ignition — it may not reliably self-ignite." : "A normal diesel range.");
      return `${warn} A longer rod (higher L/a) reduces the secondary shake: this one runs <b>${fmt(1 / a.rod_ratio, 3)}</b> of the primary.`;
    },
  },

  {
    id: "aspiration",
    eyebrow: "Induction",
    title: "How is it fed?",
    blurb: "Boost packs a denser charge in. Who pays for the compression is the difference between the two forced options.",
    controls: [{
      kind: "choice", key: "aspiration", columns: 3,
      options: [
        { value: "naturally_aspirated", label: "Natural", sub: "atmospheric" },
        { value: "turbocharged", label: "Turbo", sub: "exhaust driven" },
        { value: "supercharged", label: "Supercharged", sub: "belt driven" },
      ],
    }],
    apply: (a, v) => {
      if (v === "naturally_aspirated") { a.manifold_bar = 1.0; a.intake_temperature_K = 330; }
      else if (!a.manifold_bar || a.manifold_bar <= 1.0) { a.manifold_bar = 1.8; a.intake_temperature_K = 320; }
    },
    note: (a) => a.aspiration === "supercharged"
      ? "A supercharger's compression work is taken straight off the crank, so it is debited from brake power here."
      : a.aspiration === "turbocharged"
        ? "Driven by exhaust energy, so it costs the crank nothing — but the turbine can only make that power by expanding the exhaust across itself, and that back-pressure is solved from the turbo's shaft power balance and charged to the pumping loop."
        : "Manifold pressure sits at ambient; throttling below it costs pumping work.",
  },

  {
    id: "boost",
    eyebrow: "Induction",
    title: "How much boost, and how cool?",
    blurb: "Manifold pressure sets the charge density. Intercooling brings the charge temperature back down, which is what keeps it out of knock.",
    when: (a) => a.aspiration !== "naturally_aspirated",
    controls: [
      { kind: "range", key: "manifold_bar", min: 1.0, max: 3.0, step: 0.05, unit: " bar", label: "Manifold pressure (absolute)" },
      { kind: "range", key: "intake_temperature_K", min: 290, max: 420, step: 5, unit: " K", label: "Charge temperature after intercooling" },
    ],
    note: (a) => `Gauge boost <b>${fmt(a.manifold_bar - 1, 2)} bar</b> (${fmt((a.manifold_bar - 1) * 14.5038, 1)} psi). ${a.intake_temperature_K > 360 ? "A hot charge like this brings knock on early." : "Well intercooled."}`,
  },

  {
    id: "head",
    eyebrow: "Breathing",
    title: "How many valves per cylinder?",
    blurb: "Valve curtain area is what the cylinder breathes through. Once the piston demands more than the port can pass, the inlet chokes and volumetric efficiency falls away.",
    controls: [{
      kind: "choice", key: "head", columns: 3,
      options: [
        { value: "two", label: "2-valve", sub: "one in, one out" },
        { value: "four", label: "4-valve", sub: "two in, two out" },
        { value: "five", label: "5-valve", sub: "three in, two out" },
      ],
    }],
    note: (a) => HEAD_PRESETS[a.head]?.note || "",
  },

  {
    id: "cam",
    eyebrow: "Breathing",
    title: "Which camshaft?",
    blurb: "Valve timing sets where the closed cycle begins and ends. Closing the intake later fills better at speed but throws away effective compression down low.",
    controls: [{
      kind: "choice", key: "cam", columns: 3,
      options: [
        { value: "economy", label: "Economy", sub: "short duration" },
        { value: "street", label: "Street", sub: "road cam" },
        { value: "sport", label: "Sport", sub: "more overlap" },
        { value: "race", label: "Race", sub: "big duration" },
        { value: "miller", label: "Miller", sub: "very late IVC" },
      ],
    }],
    note: (a) => {
      const c = CAM_PRESETS[a.cam];
      if (!c) return "";
      return `${c.note}<br />IVO ${c.ivo}° BTDC · IVC ${c.ivc}° ABDC · EVO ${c.evo}° BBDC · EVC ${c.evc}° ATDC — <b>${c.ivo + c.evc}°</b> overlap.`;
    },
  },

  {
    id: "exhaust",
    eyebrow: "Breathing",
    title: "What comes out the back?",
    blurb: "Every restriction downstream raises the pressure the piston has to push against on the exhaust stroke, and that comes straight off brake power.",
    controls: [{
      kind: "choice", key: "exhaust", columns: 4,
      options: Object.entries(EXHAUST_PRESETS).map(([k, v]) => ({ value: k, label: v.label, sub: v.sub })),
    }],
  },

  {
    id: "operating",
    eyebrow: "Operating point",
    title: "Where is it running?",
    blurb: "The cycle is solved at one speed and one mixture strength. The dyno sweep in the console will walk the rev range afterwards.",
    controls: [
      { kind: "range", key: "rpm", min: 800, max: 12000, step: 100, unit: " rpm", label: "Engine speed" },
      { kind: "range", key: "equivalence_ratio", min: 0.4, max: 1.4, step: 0.01, unit: "", label: "Equivalence ratio φ" },
    ],
    note: (a) => {
      const { stroke } = boreStroke(a);
      const meanPS = (2 * stroke * a.rpm) / 60;
      const lam = 1 / a.equivalence_ratio;
      const mix = lam > 1.03 ? "lean" : lam < 0.97 ? "rich" : "stoichiometric";
      return `λ = <b>${fmt(lam, 2)}</b> (${mix}). Mean piston speed <b>${fmt(meanPS, 1)} m/s</b>.`;
    },
  },
];

/* =============================================================
   RUNTIME
   ============================================================= */

const DEFAULTS = {
  character: "road",
  ignition: "spark",
  fuel: "gasoline",
  layout_kind: "inline",
  cylinders: 4,
  bank_angle_deg: 0,
  crankpin_offset_deg: 0,
  crank_type: "flat_plane",
  displacement_L: 2.0,
  bore_stroke_ratio: 1.0,
  compression_ratio: 11,
  rod_ratio: 3.5,
  strokes_per_cycle: 4,
  aspiration: "naturally_aspirated",
  manifold_bar: 1.0,
  intake_temperature_K: 330,
  head: "four",
  cam: "street",
  exhaust: "stock",
  rpm: 5000,
  equivalence_ratio: 1.0,
  combustion_start_deg: -15,
  burn_duration_deg: 50,
};

let answers = { ...DEFAULTS };
let cursor = 0;
let onDone = null;
let reviewData = null;

const visible = () => STEPS.filter((s) => !s.when || s.when(answers));

/** Translate the wizard's answers into a /piston/simulate payload. */
export function specFromAnswers(a = answers) {
  const cam = CAM_PRESETS[a.cam] || CAM_PRESETS.street;
  const head = HEAD_PRESETS[a.head] || HEAD_PRESETS.four;
  const exhaust = EXHAUST_PRESETS[a.exhaust] || EXHAUST_PRESETS.stock;
  return {
    fuel: a.fuel,
    cylinders: a.cylinders,
    strokes_per_cycle: a.strokes_per_cycle,
    displacement_L: a.displacement_L,
    bore_stroke_ratio: a.bore_stroke_ratio,
    compression_ratio: a.compression_ratio,
    rod_ratio: a.rod_ratio,
    rpm: a.rpm,
    equivalence_ratio: a.equivalence_ratio,
    combustion_start_deg: a.combustion_start_deg,
    burn_duration_deg: a.burn_duration_deg,
    aspiration: a.aspiration,
    intake_pressure_Pa: a.manifold_bar * 1e5,
    intake_temperature_K: a.intake_temperature_K,
    layout: {
      kind: a.layout_kind,
      bank_angle_deg: a.layout_kind === "vee" || a.layout_kind === "w" ? a.bank_angle_deg : 0,
      crankpin_offset_deg: a.layout_kind === "vee" || a.layout_kind === "w" ? a.crankpin_offset_deg : 0,
      crank_type: a.crank_type,
    },
    valve_timing: {
      intake_open_btdc_deg: cam.ivo,
      intake_close_abdc_deg: cam.ivc,
      exhaust_open_bbdc_deg: cam.evo,
      exhaust_close_atdc_deg: cam.evc,
    },
    valve_geometry: {
      intake_valves_per_cylinder: head.niv,
      exhaust_valves_per_cylinder: head.nev,
      intake_valve_diameter_ratio: head.div,
      exhaust_valve_diameter_ratio: head.dev,
      max_lift_ratio: 0.25,
      discharge_coefficient: 0.35,
      exhaust_restriction: exhaust.value,
    },
    include_trace: false,
  };
}

async function postSpec(spec) {
  const res = await fetch(API_SIM, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(spec),
  });
  const text = await res.text();
  let payload = {};
  try { payload = text ? JSON.parse(text) : {}; } catch { throw new Error(`Server error ${res.status}`); }
  if (!res.ok) {
    const d = payload?.detail;
    throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg || x).join("; ") : `Request failed (${res.status})`);
  }
  return payload;
}

/* ---------- rendering ---------- */

function controlHtml(ctl) {
  const key = ctl.key;
  const value = answers[key];
  if (ctl.kind === "choice") {
    const opts = typeof ctl.options === "function" ? ctl.options(answers) : ctl.options;
    return `<div class="bd-choices" data-cols="${ctl.columns || 2}">` + opts.map((o) => `
      <button type="button" class="bd-choice${String(o.value) === String(value) ? " is-active" : ""}"
              data-key="${key}" data-value="${esc(o.value)}"${ctl.numeric ? ' data-numeric="1"' : ""}>
        <span class="bd-choice-label">${esc(o.label)}</span>
        <span class="bd-choice-sub">${esc(o.sub || "")}</span>
        ${o.desc ? `<span class="bd-choice-desc">${esc(o.desc)}</span>` : ""}
      </button>`).join("") + `</div>`;
  }
  if (ctl.kind === "range") {
    const dp = ctl.step < 0.1 ? 2 : ctl.step < 1 ? 1 : 0;
    return `
      <label class="bd-range">
        <span class="bd-range-head">
          <span>${esc(ctl.label)}</span>
          <b id="bdOut_${key}">${fmt(value, dp)}${esc(ctl.unit || "")}</b>
        </span>
        <input type="range" data-key="${key}" data-dp="${dp}" data-unit="${esc(ctl.unit || "")}"
               min="${ctl.min}" max="${ctl.max}" step="${ctl.step}" value="${value}" />
      </label>`;
  }
  return "";
}

function reviewHtml() {
  const a = answers;
  const { bore, stroke } = boreStroke(a);
  const cam = CAM_PRESETS[a.cam], head = HEAD_PRESETS[a.head];
  const rows = [
    ["Arrangement", `${a.layout_kind === "vee" ? `${fmt(a.bank_angle_deg, 0)}° V${a.cylinders}` : a.layout_kind === "flat" ? `flat-${a.cylinders}` : a.layout_kind === "inline" ? `inline-${a.cylinders}` : `${a.cylinders}-cyl ${a.layout_kind}`}`],
    ["Capacity", `${fmt(a.displacement_L, 2)} L · ${fmt(bore * 1000, 1)} × ${fmt(stroke * 1000, 1)} mm`],
    ["Compression", `${fmt(a.compression_ratio, 1)}:1 geometric`],
    ["Fuel", `${a.fuel} · φ ${fmt(a.equivalence_ratio, 2)}`],
    ["Induction", a.aspiration === "naturally_aspirated" ? "naturally aspirated" : `${a.aspiration.replace("charged", "charged")} · ${fmt(a.manifold_bar, 2)} bar`],
    ["Head", `${head.label} · ${cam.label} cam`],
    ["Exhaust", EXHAUST_PRESETS[a.exhaust].label],
    ["Speed", `${fmt(a.rpm, 0)} rpm`],
  ];
  const spec = `<div class="bd-spec">${rows.map(([k, v]) => `<div class="bd-spec-row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("")}</div>`;

  if (!reviewData) {
    return spec + `<p class="bd-note" id="bdReviewNote">Solving your engine…</p>`;
  }
  if (reviewData.error) {
    return spec + `<p class="bd-note bd-error">${esc(reviewData.error)}</p>`;
  }
  const r = reviewData;
  const L = r.layout || {};
  const hp = (r.brake_power_W || 0) * 1.34102209e-3;
  const metrics = [
    ["Brake power", `${fmt(r.brake_power_W / 1000, 1)} kW`, `${fmt(hp, 0)} hp`],
    ["Brake torque", `${fmt(r.brake_torque_Nm, 0)} N·m`, ""],
    ["BMEP", `${fmt(r.bmep_Pa / 1e5, 1)} bar`, ""],
    ["Effective CR", `${fmt(r.effective_compression_ratio, 2)}:1`, `geometric ${fmt(a.compression_ratio, 1)}`],
    ["Volumetric eff.", `${fmt(r.volumetric_efficiency * 100, 1)} %`, `inlet Mach ${fmt(r.inlet_mach_index, 2)}`],
    ["Firing", L.even_fire ? "even" : "uneven", `every ${L.firing_intervals_deg ? fmt(L.firing_intervals_deg[0], 0) : "—"}°`],
  ];
  const warn = (r.operating_warnings || []).map((w) =>
    `<div class="bd-warn ${esc(w.severity)}"><b>${esc(w.kind.replace("_", " "))}</b><span>${esc(w.message)}</span></div>`).join("");

  return spec + `
    <div class="bd-metrics">${metrics.map(([k, v, s]) => `
      <div class="bd-metric"><span>${esc(k)}</span><b>${esc(v)}</b>${s ? `<i>${esc(s)}</i>` : ""}</div>`).join("")}</div>
    ${warn}
    <div class="bd-verdicts">
      <p><span>Balance</span>${esc(L.balance_verdict || "—")}</p>
      <p><span>Breathing</span>${esc(r.breathing_verdict || "—")}</p>
    </div>`;
}

function render() {
  const steps = visible();
  const isReview = cursor >= steps.length;
  const step = isReview ? null : steps[cursor];
  const total = steps.length + 1;
  const idx = Math.min(cursor, steps.length);

  const body = document.getElementById("bdBody");
  const dots = document.getElementById("bdProgress");
  if (!body) return;

  dots.innerHTML = Array.from({ length: total }, (_, i) =>
    `<span class="bd-dot${i === idx ? " is-active" : i < idx ? " is-done" : ""}"></span>`).join("");

  if (isReview) {
    body.innerHTML = `
      <p class="bd-eyebrow">Review</p>
      <h2 class="bd-title">Your engine</h2>
      <p class="bd-blurb">Solved by the same crank-angle integrator the console uses. Build it to load every value into the console and keep going.</p>
      ${reviewHtml()}`;
  } else {
    const note = step.note ? step.note(answers) : "";
    body.innerHTML = `
      <p class="bd-eyebrow">${esc(step.eyebrow)} <span class="bd-step-count">${idx + 1} / ${total}</span></p>
      <h2 class="bd-title">${esc(step.title)}</h2>
      <p class="bd-blurb">${esc(step.blurb)}</p>
      ${step.controls.map(controlHtml).join("")}
      ${note ? `<p class="bd-note">${note}</p>` : ""}`;
  }

  document.getElementById("bdBack").disabled = cursor === 0;
  const nextBtn = document.getElementById("bdNext");
  nextBtn.textContent = isReview ? "Build it" : "Continue";
  nextBtn.className = isReview ? "primary-button" : "ghost-btn";
  wireControls();
}

function wireControls() {
  document.querySelectorAll("#bdBody .bd-choice").forEach((b) => {
    b.addEventListener("click", () => {
      const key = b.dataset.key;
      const raw = b.dataset.value;
      const value = b.dataset.numeric ? Number(raw) : raw;
      answers[key] = value;
      const steps = visible();
      const step = steps[cursor];
      const ctl = step?.controls.find((c) => c.key === key);
      if (step?.apply) step.apply(answers, value);
      render();
    });
  });
  document.querySelectorAll("#bdBody input[type=range]").forEach((el) => {
    el.addEventListener("input", () => {
      const key = el.dataset.key;
      answers[key] = Number(el.value);
      const dp = Number(el.dataset.dp || 0);
      const out = document.getElementById(`bdOut_${key}`);
      if (out) out.textContent = `${fmt(answers[key], dp)}${el.dataset.unit || ""}`;
      // Refresh only the live note, so dragging never rebuilds the slider.
      const step = visible()[cursor];
      const noteEl = document.querySelector("#bdBody .bd-note");
      if (step?.note && noteEl) noteEl.innerHTML = step.note(answers);
    });
  });
}

async function loadReview() {
  reviewData = null;
  render();
  try {
    reviewData = await postSpec(specFromAnswers());
  } catch (err) {
    reviewData = { error: err.message };
  }
  render();
}

function close() {
  const root = document.getElementById("builderOverlay");
  if (root) root.hidden = true;
  document.body.style.overflow = "";
}

/** Open the wizard. `onComplete(spec, result)` fires when the user builds. */
export function openBuilder(onComplete) {
  onDone = onComplete;
  answers = { ...DEFAULTS };
  cursor = 0;
  reviewData = null;
  const root = document.getElementById("builderOverlay");
  root.hidden = false;
  document.body.style.overflow = "hidden";
  render();
}

export function initBuilder() {
  const root = document.getElementById("builderOverlay");
  if (!root) return;

  document.getElementById("bdClose").addEventListener("click", close);
  document.getElementById("bdBack").addEventListener("click", () => {
    if (cursor > 0) { cursor -= 1; reviewData = null; render(); }
  });
  document.getElementById("bdNext").addEventListener("click", async () => {
    const steps = visible();
    if (cursor < steps.length) {
      cursor += 1;
      if (cursor >= steps.length) { await loadReview(); }
      else render();
      return;
    }
    // Review -> build.
    if (reviewData && !reviewData.error) {
      close();
      if (onDone) onDone(specFromAnswers(), reviewData);
    }
  });
  root.addEventListener("click", (e) => { if (e.target === root) close(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !root.hidden) close();
  });
}

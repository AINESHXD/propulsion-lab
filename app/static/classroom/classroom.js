/* PropulsionLab Classroom — guided design challenges.
 *
 * One problem per engine family. Each problem fixes a flight condition, exposes
 * a few design variables, and grades the result against targets by calling the
 * same /simulate endpoints the console uses. No state is stored server-side. */

const PROBLEMS = [
  {
    engine: "Turbojet",
    endpoint: "/simulate/turbojet",
    title: "Thrust without cooking the compressor",
    scenario:
      "Design a turbojet for at least 40 kN thrust at Mach 0.8, 10 km, while keeping the " +
      "compressor-exit temperature Tt3 under 700 K (a material limit) and TSFC at or below 135 kg/kN·h.",
    fixed: { altitude_m: 10000, mach: 0.8, mass_flow_air_kg_s: 50 },
    controls: [
      { field: "compressor_pressure_ratio", label: "Compressor PR", min: 5, max: 18, step: 0.5, value: 12 },
      { field: "turbine_inlet_temperature_K", label: "Turbine inlet T (K)", min: 1100, max: 1700, step: 10, value: 1400 },
    ],
    targets: [
      { key: "thrust_kN", op: ">=", value: 40, label: "Thrust ≥ 40 kN", fmt: (v) => v.toFixed(1) + " kN" },
      { key: "station3_Tt", op: "<=", value: 700, label: "Compressor exit Tt3 ≤ 700 K", fmt: (v) => v.toFixed(0) + " K" },
      { key: "TSFC_kg_per_kN_hr", op: "<=", value: 135, label: "TSFC ≤ 135 kg/kN·h", fmt: (v) => v.toFixed(1) },
    ],
    hint:
      "Pressure ratio lifts thrust and efficiency but also Tt3; turbine-inlet temperature lifts thrust " +
      "hard with little Tt3 penalty. Lean on TIT to make thrust and keep PR moderate to hold Tt3 down.",
  },
  {
    engine: "Turbofan",
    endpoint: "/simulate/turbofan",
    title: "Cut fuel burn with bypass",
    scenario:
      "Reach TSFC at or below 78 kg/kN·h while keeping thrust at least 38 kN at Mach 0.8, 11 km.",
    fixed: { altitude_m: 11000, mach: 0.8 },
    controls: [
      { field: "bypass_ratio", label: "Bypass ratio", min: 2, max: 12, step: 0.5, value: 5 },
      { field: "fan_pressure_ratio", label: "Fan PR", min: 1.3, max: 2.0, step: 0.05, value: 1.6 },
      { field: "turbine_inlet_temperature_K", label: "Turbine inlet T (K)", min: 1400, max: 1700, step: 10, value: 1500 },
    ],
    targets: [
      { key: "TSFC_kg_per_kN_hr", op: "<=", value: 78, label: "TSFC ≤ 78 kg/kN·h", fmt: (v) => v.toFixed(1) },
      { key: "thrust_kN", op: ">=", value: 38, label: "Thrust ≥ 38 kN", fmt: (v) => v.toFixed(1) + " kN" },
    ],
    hint:
      "More bypass air moves more air slowly, raising propulsive efficiency and cutting TSFC, but it " +
      "also cuts specific thrust. Push bypass up, then raise the turbine-inlet temperature to claw the thrust back.",
  },
  {
    engine: "Turboprop",
    endpoint: "/simulate/turboprop",
    title: "Power within the blade limit",
    scenario:
      "Deliver at least 4,500 kW equivalent shaft power at Mach 0.5, 6 km. The turbine-inlet " +
      "temperature is capped at 1,500 K by a blade limit, so you can't just crank the heat, size the " +
      "airflow and pressure ratio to make the power.",
    fixed: { altitude_m: 6000, mach: 0.5 },
    controls: [
      { field: "compressor_pressure_ratio", label: "Compressor PR", min: 6, max: 18, step: 0.5, value: 10 },
      { field: "mass_flow_air_kg_s", label: "Air mass flow (kg/s)", min: 5, max: 25, step: 1, value: 12 },
      { field: "turbine_inlet_temperature_K", label: "Turbine inlet T (K)", min: 1100, max: 1500, step: 10, value: 1300 },
    ],
    targets: [
      { key: "equivalent_shaft_power_kW", op: ">=", value: 4500, label: "Equivalent shaft power ≥ 4500 kW", fmt: (v) => v.toFixed(0) + " kW" },
    ],
    hint:
      "Shaft power scales with the air mass flow and the heat added. With the turbine temperature " +
      "capped, your biggest lever is mass flow, push it up, and lift the pressure ratio to use the heat well.",
  },
  {
    engine: "Ramjet",
    endpoint: "/simulate/ramjet",
    title: "Find where a ramjet earns its keep",
    scenario:
      "A ramjet has no compressor, it relies on ram compression, so it makes little thrust at low " +
      "speed. Find a flight Mach where it produces at least 28 kN with overall efficiency of 15% or more.",
    fixed: { altitude_m: 12000, mass_flow_air_kg_s: 40 },
    controls: [
      { field: "mach", label: "Flight Mach", min: 1.0, max: 4.0, step: 0.1, value: 1.0 },
      { field: "combustor_exit_temperature_K", label: "Combustor exit T (K)", min: 1800, max: 2400, step: 25, value: 2000 },
    ],
    targets: [
      { key: "thrust_kN", op: ">=", value: 28, label: "Thrust ≥ 28 kN", fmt: (v) => v.toFixed(1) + " kN" },
      { key: "overall_efficiency_estimate", op: ">=", value: 0.15, label: "Overall efficiency ≥ 15%", fmt: (v) => (v * 100).toFixed(0) + " %" },
    ],
    hint:
      "Thrust climbs steeply with Mach as ram compression builds. Below about Mach 2 a ramjet barely " +
      "works; push the flight Mach up and keep the combustor hot.",
  },
  {
    engine: "Scramjet",
    endpoint: "/simulate/scramjet",
    title: "Hypersonic, with the air still supersonic",
    scenario:
      "A scramjet burns in a supersonic stream, only viable at hypersonic speed, and its thrust falls " +
      "as Mach climbs. Staying at Mach 6 or above, find the operating point that makes at least 18 kN " +
      "thrust at 42% overall efficiency or better.",
    fixed: { altitude_m: 26000, mass_flow_air_kg_s: 40 },
    controls: [
      { field: "mach", label: "Flight Mach", min: 4, max: 9, step: 0.25, value: 8 },
      { field: "equivalence_ratio", label: "Equivalence ratio φ", min: 0.3, max: 1.2, step: 0.05, value: 0.8 },
    ],
    targets: [
      { key: "mach_input", op: ">=", value: 6, label: "Flight Mach ≥ 6", fmt: (v) => v.toFixed(2) },
      { key: "thrust_kN", op: ">=", value: 18, label: "Thrust ≥ 18 kN", fmt: (v) => v.toFixed(1) + " kN" },
      { key: "overall_efficiency_estimate", op: ">=", value: 0.42, label: "Overall efficiency ≥ 42%", fmt: (v) => (v * 100).toFixed(0) + " %" },
    ],
    hint:
      "At the top of the Mach range thrust and efficiency both sag. Come down toward Mach 6–7 where the " +
      "cycle is happiest, and trim the equivalence ratio.",
  },
];

const compare = (a, op, b) =>
  op === ">=" ? a >= b : op === "<=" ? a <= b : op === ">" ? a > b : op === "<" ? a < b : a === b;

function metricFrom(result, payload, key) {
  if (key === "station3_Tt") return result.station_table?.["3"]?.stagnation_temperature_K;
  if (key === "mach_input") return payload.mach;
  return result[key];
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function renderProblem(problem) {
  const card = el("article", "card");
  card.dataset.engine = problem.engine;

  const head = el("div", "card-head");
  head.append(el("span", "card-eng", problem.engine), el("h2", null, problem.title));
  card.append(head);
  card.append(el("p", "scenario", problem.scenario));

  const controls = el("div", "controls");
  const inputs = {};
  for (const c of problem.controls) {
    const wrap = el("div", "control");
    const label = el("label", null, c.label);
    const input = el("input");
    input.type = "number";
    input.min = c.min; input.max = c.max; input.step = c.step; input.value = c.value;
    inputs[c.field] = input;
    wrap.append(label, input);
    controls.append(wrap);
  }
  card.append(controls);

  const actions = el("div", "actions");
  const checkBtn = el("button", "btn", "Check answer");
  const hintBtn = el("button", "hint-toggle", "Show hint");
  actions.append(checkBtn, hintBtn);
  card.append(actions);

  const hint = el("p", "hint", problem.hint);
  hint.hidden = true;
  hintBtn.addEventListener("click", () => {
    hint.hidden = !hint.hidden;
    hintBtn.textContent = hint.hidden ? "Show hint" : "Hide hint";
  });
  card.append(hint);

  const results = el("div", "results");
  card.append(results);

  checkBtn.addEventListener("click", async () => {
    checkBtn.disabled = true;
    checkBtn.textContent = "Checking…";
    const payload = { ...problem.fixed };
    for (const c of problem.controls) payload[c.field] = Number(inputs[c.field].value);
    try {
      const response = await fetch(problem.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const text = await response.text();
      if (!response.ok) {
        let detail = `Server error ${response.status}.`;
        try { detail = JSON.parse(text).detail || detail; } catch { /* keep */ }
        throw new Error(typeof detail === "string" ? detail : "Invalid input.");
      }
      const result = JSON.parse(text);
      showResults(results, problem, result, payload);
    } catch (err) {
      results.className = "results show";
      results.replaceChildren(el("div", "verdict fail", `Could not run: ${err.message}`));
    } finally {
      checkBtn.disabled = false;
      checkBtn.textContent = "Check answer";
    }
  });

  return card;
}

function showResults(host, problem, result, payload) {
  host.replaceChildren();
  host.className = "results show";
  const rows = [];
  let allMet = true;
  for (const t of problem.targets) {
    const got = metricFrom(result, payload, t.key);
    const met = got != null && compare(got, t.op, t.value);
    if (!met) allMet = false;
    const row = el("div", `target ${met ? "met" : "miss"}`);
    row.append(el("span", "mark", met ? "✓" : "✕"));
    row.append(el("span", "label", t.label));
    row.append(el("span", "got", got == null ? "n/a" : `you: ${t.fmt(got)}`));
    rows.push(row);
  }
  const verdict = el("div", `verdict ${allMet ? "pass" : "fail"}`,
    allMet ? "Solved — every target met." : "Not yet — tune the variables and check again.");
  host.append(verdict);
  const list = el("div", "targets");
  rows.forEach((r) => list.append(r));
  host.append(list);
}

function start() {
  const problemsHost = document.getElementById("problems");
  const filtersHost = document.getElementById("filters");
  const engines = ["All", ...PROBLEMS.map((p) => p.engine)];

  engines.forEach((name, i) => {
    const btn = el("button", "filter" + (i === 0 ? " on" : ""), name);
    btn.dataset.engine = name;
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter").forEach((b) => b.classList.remove("on"));
      btn.classList.add("on");
      document.querySelectorAll("#problems .card").forEach((c) => {
        c.style.display = name === "All" || c.dataset.engine === name ? "" : "none";
      });
    });
    filtersHost.append(btn);
  });

  PROBLEMS.forEach((p) => problemsHost.append(renderProblem(p)));
}

start();

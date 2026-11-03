// PistonLab engine kinematics for the 3D page. Everything comes from one /piston/simulate response: bore, stroke,
// rod ratio and compression ratio from the inputs the solver used, the cylinder map and firing order from its layout
// analysis, and the chamber pressure, temperature and burn from its trace. Engine space is metres: crank axis on z
// (front = +z), y up, angles measured from vertical toward +x, the same convention as app/engine_core/piston/layout.py.
const D2R = Math.PI / 180;
export const mod = (a, m) => ((a % m) + m) % m;

// Cylinder pitch along the crank, in bores. The layout gives stations in bore spacings; real blocks sit 1.1 to 1.25
// bores apart, so 1.18 keeps the liners from touching without stretching the engine.
const PITCH = 1.18;

/**
 * input: the request body that was solved; out: the solver's response (with trace and layout); hw: the hardware the
 * solver does not model (valvetrain type, oil system, balance shafts), from the gallery or inferred.
 * Returns the engine description every other module reads.
 */
export function makeEngine(input, out, hw = {}) {
  const bore = out.bore_m;
  const stroke = out.stroke_m;
  const r = stroke / 2;
  const rodRatio = input.rod_ratio ?? 3.5;
  const L = rodRatio * r;
  const cr = input.compression_ratio ?? 10.5;
  const area = (Math.PI / 4) * bore * bore;
  const swept = area * stroke;
  const vc = swept / (cr - 1);
  // the head face sits one flat-head clearance height above the crown at TDC
  const clearH = stroke / (cr - 1);
  const crownH = 0.34 * bore; // wrist pin to crown
  const sTDC = L + r;
  const sBDC = L - r;
  const deck = sTDC + crownH + clearH;

  const map = out.layout?.cylinder_map ?? [{number: 1, bank: 0, axis_deg: 0, pin_deg: 0, phase_deg: 0, station: 0, firing_deg: 0}];
  const order = out.layout?.firing_order ?? [1];
  const cyl = map.map((c) => {
    const a = c.axis_deg * D2R;
    return {
      n: c.number,
      bank: c.bank,
      axis: c.axis_deg,
      pin: c.pin_deg,
      fire: c.firing_deg,
      z: -c.station * PITCH * bore,
      b: [Math.sin(a), Math.cos(a)], // along the bore, toward the head
      p: [Math.cos(a), -Math.sin(a)], // across the bore
    };
  });
  // firing measured from cylinder 1, so the page opens with cylinder 1 at its firing TDC when th = fire of 1
  const fire0 = cyl[0].fire;

  const vt = {intake_open_btdc_deg: 10, intake_close_abdc_deg: 40, exhaust_open_bbdc_deg: 45, exhaust_close_atdc_deg: 10, ...(input.valve_timing || {})};
  const vg = {intake_valves_per_cylinder: 2, exhaust_valves_per_cylinder: 2, intake_valve_diameter_ratio: 0.38, exhaust_valve_diameter_ratio: 0.33, max_lift_ratio: 0.25, ...(input.valve_geometry || {})};
  // valve events in degrees after the firing TDC
  const EX = [180 - vt.exhaust_open_bbdc_deg, 360 + vt.exhaust_close_atdc_deg];
  const IN = [360 - vt.intake_open_btdc_deg, 540 + vt.intake_close_abdc_deg];

  // the closed part of the cycle from the solver trace: theta -180..180 with firing TDC at 0
  const tr = out.trace || [];
  const T0 = tr.length ? tr[0].theta_deg : -180;
  const dT = tr.length > 1 ? tr[1].theta_deg - tr[0].theta_deg : 1;
  const sample = (key, theta) => {
    if (!tr.length) return 0;
    const x = (theta - T0) / dT;
    const i = Math.max(0, Math.min(tr.length - 2, Math.floor(x)));
    const k = Math.max(0, Math.min(1, x - i));
    return tr[i][key] + (tr[i + 1][key] - tr[i][key]) * k;
  };
  const pIn = out.boost_pressure_Pa > 0 ? out.boost_pressure_Pa : input.intake_pressure_Pa ?? 1e5;
  const pEx = out.exhaust_pressure_Pa || 1e5;
  const tEx = out.exhaust_temperature_K || 900;
  const tIn = out.mixed_temperature_K || input.intake_temperature_K || 330;
  const pEnd = sample('pressure_Pa', 180);
  const tEnd = sample('temperature_K', 180);

  const blend = (a, b, k) => a + (b - a) * Math.max(0, Math.min(1, k));
  /** chamber state at phase ps (degrees after firing TDC): pressure Pa, temperature K, burned fraction */
  const gas = (ps) => {
    ps = mod(ps, 720);
    if (ps <= 180 || ps >= 540) {
      const th = ps >= 540 ? ps - 720 : ps;
      return {p: sample('pressure_Pa', th), T: sample('temperature_K', th), xb: sample('burned_fraction', th)};
    }
    // gas exchange is not in the trace: blowdown to the exhaust pressure, then the intake pressure
    if (ps < 360) {
      const k = (ps - 180) / 40;
      return {p: blend(pEnd, pEx, k), T: blend(tEnd, tEx, k), xb: 1};
    }
    const k = (ps - 360) / 30;
    return {p: blend(pEx, pIn, k), T: blend(tEx, tIn, k * 2), xb: Math.max(0, 1 - k * 1.5)};
  };

  const pistonS = (c, th) => {
    const a = (th + c.pin) * D2R;
    const P = [r * Math.sin(a), r * Math.cos(a)];
    const pb = P[0] * c.b[0] + P[1] * c.b[1];
    const pp = P[0] * c.p[0] + P[1] * c.p[1];
    return {s: pb + Math.sqrt(L * L - pp * pp), P};
  };
  const strokes = input.strokes_per_cycle ?? 4;
  const cycle = strokes === 2 ? 360 : 720;
  const psi = (c, th) => mod(th - c.fire, cycle);
  const volume = (c, th) => vc + area * (sTDC - pistonS(c, th).s);
  const bump = (ps, [a, b]) => {
    const x = mod(ps - a, 720) / (b - a);
    return x >= 0 && x <= 1 ? Math.sin(Math.PI * x) ** 2 : 0;
  };

  return {
    bore, stroke, r, L, cr, area, swept, vc, crownH, clearH, sTDC, sBDC, deck, rodRatio,
    cyl, order, fire0, strokes, cycle, EX, IN, vt, vg, pIn, pEx,
    gas, pistonS, psi, volume,
    liftEx: (ps) => bump(ps, EX),
    liftIn: (ps) => bump(ps, IN),
    rpm: input.rpm ?? 3000,
    hw: hardware(hw, vg, input),
    out, input,
  };
}

export const STROKES = ['POWER', 'EXHAUST', 'INTAKE', 'COMPRESSION'];
export const strokeOf = (ps) => STROKES[Math.floor(mod(ps, 720) / 180)];
/** the charge colour key: 0 fresh charge, 1 compressed, 2 burning or burned, 3 exhaust */
export const chargeOf = (ps, xb) => {
  ps = mod(ps, 720);
  if (ps < 180) return 2;
  if (ps < 360) return 3;
  if (ps < 540) return 0;
  return xb > 0.02 ? 2 : 1;
};

/** Valvetrain, oil system and balance shafts: what was given, else what an engine like this usually has. */
function hardware(hw, vg, input) {
  const valves = vg.intake_valves_per_cylinder + vg.exhaust_valves_per_cylinder;
  let valvetrain = hw.valvetrain ?? (valves <= 2 ? 'sohc' : 'dohc');
  // one overhead cam or a block cam can only work valves set in a line under it
  if (valvetrain !== 'dohc' && valves > 2) valvetrain = 'dohc';
  return {
    valvetrain,
    rocker_ratio: hw.rocker_ratio ?? 1.6,
    oil: hw.oil ?? 'wet',
    balance_shafts: hw.balance_shafts ?? 0,
    note: hw.note ?? '',
    // grey cast iron or a sand-cast aluminium alloy; a custom engine is drawn in aluminium
    block: hw.block === 'iron' ? 'iron' : 'aluminium',
    turbo: input.aspiration === 'turbocharged',
    // a Formula 1 power unit: split turbo with MGU-H, MGU-K, carbon intake, no belt drive (see engine.js)
    f1: hw.power_unit === 'f1',
    diesel: input.fuel === 'diesel',
  };
}

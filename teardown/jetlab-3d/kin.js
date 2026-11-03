// The gas path, laid out from the cycle solve. Each station's annulus area is the area that passes the solver's mass
// flow at that station's stagnation state and an assumed axial Mach number (typical design values, listed in AX_MACH):
//     A = m * sqrt(Tt) / (Pt * MFP(M, gamma))
// Areas are then scaled together so the fan (or inlet) matches the engine's published diameter, which keeps every
// ratio between stations the solver's and the overall size the real engine's. Blade rows, discs and casings are
// placed on the radii this gives; stage and blade counts and spool speeds come from published data (gallery.json).
// Everything here is plain numbers: no three.js.

export const mod = (a, n) => ((a % n) + n) % n;
const R_AIR = 287.05;
const lerp = (a, b, t) => a + (b - a) * t;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));

/** mass-flow parameter m*sqrt(Tt)/(A*Pt) at Mach M, in SI */
export const mfp = (M, g = 1.4) => Math.sqrt(g / R_AIR) * M * Math.pow(1 + ((g - 1) / 2) * M * M, -(g + 1) / (2 * (g - 1)));
/** static temperature and flow speed at Mach M from the stagnation temperature */
const flowAt = (Tt, M, g) => {
  const T = Tt / (1 + ((g - 1) / 2) * M * M);
  return {T, V: M * Math.sqrt(g * R_AIR * T)};
};

// assumed axial Mach numbers at each station (design-point values typical of each component)
export const AX_MACH = {fan: 0.6, booster: 0.5, hpcIn: 0.48, hpcOut: 0.28, comb: 0.12, hptIn: 0.3, lptIn: 0.38, lptOut: 0.45, bypass: 0.5};

/** stagnation state for a station number, falling back to the nearest station the solver gave */
const stationOf = (out, n, fallback) => {
  const s = out.station_table[n] ?? out.station_table[String(n)] ?? (fallback != null ? out.station_table[fallback] ?? out.station_table[String(fallback)] : null);
  return s ? {Tt: s.stagnation_temperature_K, Pt: s.stagnation_pressure_Pa, M: s.mach, V: s.velocity_m_s, name: s.name} : null;
};

/**
 * Build the engine description for one solve.
 * family: turbofan | turbojet | turboprop | ramjet | scramjet; input: what was sent to the solver; out: its answer;
 * hw: hardware from the gallery (diameter, stage and blade counts, spool speeds, layout choices).
 */
export function makeJet(family, input, out, hw) {
  const J = {family, input, out, hw, stations: [], modules: [], spools: {}, paths: {}};
  const st = (n, fb) => stationOf(out, n, fb);
  const f = out.fuel_air_ratio ?? 0;
  const ex = out.extra ?? {};
  const mTot = input.total_mass_flow_air_kg_s ?? input.mass_flow_air_kg_s ?? 50;
  const mCore = ex.core_mass_flow_kg_s ?? (family === 'turbofan' ? mTot / (1 + (input.bypass_ratio ?? 0)) : mTot);
  const mByp = ex.bypass_mass_flow_kg_s ?? mTot - mCore;
  J.mTot = mTot;
  J.mach = stationOf(out, 0)?.M ?? input.mach ?? 0;
  J.mCore = mCore;
  J.mByp = mByp;
  const area = (s, m, M, g = 1.4) => (s ? (m * Math.sqrt(s.Tt)) / (s.Pt * mfp(M, g)) : 0);

  // ---------------------------------------------------------------- spool speeds (rpm) and their angular rates
  for (const [k, rpm] of Object.entries(hw.spools || {})) J.spools[k] = {rpm, w: (rpm * 2 * Math.PI) / 60};

  // ---------------------------------------------------------------- the gas path, family by family
  const D = hw.diameter_m;
  const R = D / 2;
  // each station on the path: z (axial, front is +z), hub and tip radius, the gas state there
  const pt = (id, z, rh, rt, s, M, g, label) => {
    const fl = s ? flowAt(s.Tt, M, g) : {T: 0, V: 0};
    const p = {id, z, rh, rt, Tt: s?.Tt ?? 0, Pt: s?.Pt ?? 0, M, V: fl.V, T: fl.T, label};
    J.stations.push(p);
    return p;
  };

  if (family === 'turbofan' || family === 'turbojet' || family === 'turboprop') {
    const s2 = st(2, 0);
    const s13 = st(13, 2);
    const s3 = st(3);
    const s4 = st(4);
    const s45 = st(45, 5);
    const s5 = st(5);
    const s9 = st(9, 5);
    const s19 = st(19, 13);
    const fan = family === 'turbofan';
    const hub = hw.hub_tip ?? (fan ? 0.3 : 0.45);
    // scale: real fan (or compressor face) area over the solver's area at the same station
    const A2 = area(s2, mTot, AX_MACH.fan);
    const Aface = Math.PI * R * R * (1 - hub * hub);
    const k = Aface / A2;
    J.scale = k;
    const Ac = (s, m, M, g) => area(s, m, M, g) * k;
    const mh = mCore * (1 + f);
    // core inlet: for a turbofan the booster sits behind the fan hub; otherwise the compressor face is the inlet
    const A25 = Ac(fan ? s13 : s2, mCore, fan ? AX_MACH.booster : AX_MACH.fan);
    const A3 = Ac(s3, mCore, AX_MACH.hpcOut);
    const A4 = Ac(s4, mh, AX_MACH.hptIn, 1.33);
    const A45 = Ac(s45, mh, AX_MACH.lptIn, 1.33);
    const A5 = Ac(s5, mh, AX_MACH.lptOut, 1.33);
    // the core compressor keeps a constant tip and the hub rises as the air is squeezed
    const coreTip = fan ? Math.sqrt(A25 / (Math.PI * (1 - 0.55 * 0.55))) * 0.96 : R;
    const coreHub0 = fan ? coreTip * 0.55 : R * hub;
    const coreHub3 = Math.sqrt(Math.max(coreTip * coreTip * 0.2, coreTip * coreTip - A3 / Math.PI));
    J.coreTip = coreTip;

    let z = 0;
    const chordOf = (h, ref) => clamp(0.62 * h, 0.05 * ref, 0.3 * ref);
    const rows = (kind, spool, n, rh0, rh1, rt0, rt1, Tt0, Tt1, Pt0, Pt1, opts = {}) => {
      // n stages from (rh0, rt0) to (rh1, rt1); each stage a rotor then a stator (compressor) or a stator (nozzle
      // guide vane) then a rotor (turbine)
      const stages = [];
      const z0 = z;
      for (let i = 0; i < n; i++) {
        const t = n === 1 ? 0.5 : i / (n - 1);
        const rh = lerp(rh0, rh1, t);
        const rt = lerp(rt0, rt1, t);
        const h = rt - rh;
        const c = chordOf(h, opts.ref ?? coreTip * 2) * (opts.chordK ?? 1);
        const pitch = c * 2.35;
        stages.push({i, z: z - pitch / 2, zr: z - (opts.turbine ? 0.68 : 0.27) * pitch, zs: z - (opts.turbine ? 0.27 : 0.68) * pitch, rh, rt, chord: c, pitch,
          Tt: lerp(Tt0, Tt1, (i + 0.5) / n), Pt: Pt0 * Math.pow(Pt1 / Pt0, (i + 0.5) / n),
          blades: Math.round((opts.blades0 ?? 30) + (opts.bladesK ?? 4) * i)});
        z -= pitch;
      }
      const m = {kind, spool, n, z0, z1: z, stages, Tt0, Tt1, Pt0, Pt1, ...opts};
      J.modules.push(m);
      return m;
    };

    // inlet and spinner
    J.zInlet = fan ? 0.42 * D : 0.25 * D;
    pt('inlet', J.zInlet, 0, R * 1.02, s2, AX_MACH.fan, 1.4, 'Inlet');
    if (fan) {
      const fanChord = (hw.fan_chord ?? 0.2) * D;
      z = 0;
      J.fan = {z: 0, zLE: 0, zTE: -fanChord, rh: R * hub, rt: R, chord: fanChord, blades: hw.fan_blades, spool: 'lp', Tt13: s13.Tt};
      J.modules.push({kind: 'fan', spool: 'lp', n: 1, z0: 0, z1: -fanChord, stages: [{i: 0, zr: -fanChord / 2, rh: R * hub, rt: R, chord: fanChord, blades: hw.fan_blades, Tt: s13.Tt, Pt: s13.Pt}]});
      pt('fan', 0, R * hub, R, s2, AX_MACH.fan, 1.4, 'Fan face');
      // outlet guide vanes in the bypass duct, then the splitter that divides core from bypass
      z = -fanChord - 0.06 * D;
      const zOGV = z - 0.5 * fanChord;
      J.ogv = {z: zOGV, chord: 0.45 * fanChord, n: hw.ogv ?? Math.round(hw.fan_blades * 2.2)};
      J.splitZ = -fanChord - 0.04 * D;
      // geared fan: the gearbox sits behind the fan, inside the core inlet
      if (hw.gear_ratio) {
        J.gearbox = {z: -fanChord - 0.08 * D, r: R * hub * 0.95, ratio: hw.gear_ratio, len: 0.12 * D};
      }
      z = -fanChord - 0.1 * D;
      pt('booster-in', z, coreHub0 * 0.92, coreTip * 1.04, s13, AX_MACH.booster, 1.4, 'Core inlet');
      if (hw.lpc) rows('lpc', 'lp', hw.lpc, coreHub0 * 0.92, coreHub0, coreTip * 1.04, coreTip, s13.Tt, s13.Tt * 1.15, s13.Pt, s13.Pt * 1.5, {blades0: 60, bladesK: 4});
      z -= 0.07 * D;
      // three-spool: an intermediate compressor before the HP
      if (hw.ipc) rows('ipc', 'ip', hw.ipc, coreHub0, lerp(coreHub0, coreHub3, 0.45), coreTip, coreTip * 0.97, s13.Tt * 1.15, lerp(s13.Tt, s3.Tt, 0.55), s13.Pt * 1.5, Math.sqrt(s13.Pt * s3.Pt), {blades0: 50, bladesK: 4});
    } else {
      z = 0;
      pt('fan', 0, R * hub, R, s2, AX_MACH.fan, 1.4, 'Compressor face');
    }
    // the HP (or only) compressor
    const hpcHub0 = fan ? (hw.ipc ? lerp(coreHub0, coreHub3, 0.45) : coreHub0) : R * hub;
    const hpcTip = fan ? (hw.ipc ? coreTip * 0.97 : coreTip) : R * 0.98;
    const hpcHub1 = fan ? coreHub3 : Math.sqrt(Math.max(R * R * 0.25, R * R - A3 / Math.PI));
    const ref = 2 * hpcTip;
    const nAx = family === 'turboprop' ? hw.axial ?? 3 : hw.hpc;
    const hpc = rows(family === 'turbofan' ? 'hpc' : 'compressor', 'hp', nAx, hpcHub0, hpcHub1, hpcTip, hpcTip, (hw.ipc ? lerp(s13.Tt, s3.Tt, 0.55) : fan ? s13.Tt * 1.15 : s2.Tt), s3.Tt, (hw.ipc ? Math.sqrt(s13.Pt * s3.Pt) : fan ? s13.Pt * 1.5 : s2.Pt), s3.Pt, {blades0: 36, bladesK: 5, ref, vsv: hw.vsv ?? Math.min(4, Math.ceil(nAx / 2))});
    // a turboprop finishes with a centrifugal impeller
    if (family === 'turboprop' && hw.centrifugal) {
      const r0 = hpcTip;
      const zc = z - 0.08 * D;
      J.impeller = {z: zc, rIn: hpcHub1 * 1.05, rEye: hpcTip, rOut: r0 * 1.75, len: 0.32 * D, blades: hw.impeller_blades ?? 17, spool: 'hp'};
      z = zc - 0.36 * D;
    }
    pt('hpc-exit', z, hpcHub1, hpcTip, s3, AX_MACH.hpcOut, 1.4, 'Compressor exit');
    // diffuser and combustor: an annulus radially outboard of the compressor exit, its length from residence time
    const combR0 = (J.impeller ? hpcTip * 0.9 : hpcHub1 * 0.98);
    const combR1 = (J.impeller ? J.impeller.rOut * 0.85 : hpcTip * 1.32);
    const combL = clamp((combR1 - combR0) * 2.4, 0.16 * ref, 0.6 * ref) * (hw.comb_len ?? 1);
    z -= 0.05 * ref;
    J.combustor = {z0: z, z1: z - combL, r0: combR0, r1: combR1, nozzles: hw.fuel_nozzles ?? 20, T: s4.Tt, Tin: s3.Tt};
    z -= combL;
    // turbines: HP mean radius near the compressor tip; the LP grows outward
    const hptRm = J.impeller ? hpcTip * 0.85 : hpcTip * 0.92;
    const h4 = A4 / (2 * Math.PI * hptRm);
    pt('hpt-in', z, hptRm - h4 / 2, hptRm + h4 / 2, s4, AX_MACH.hptIn, 1.33, 'Turbine inlet');
    const nH = hw.hpt ?? 1;
    const h45 = A45 / (2 * Math.PI * hptRm * 1.05);
    rows('hpt', 'hp', nH, hptRm - h4 / 2, hptRm * 1.05 - h45 / 2, hptRm + h4 / 2, hptRm * 1.05 + h45 / 2, s4.Tt, lerp(s4.Tt, s45.Tt, hw.ipt ? 0.6 : 1), s4.Pt, hw.ipt ? Math.sqrt(s4.Pt * s45.Pt) : s45.Pt, {turbine: true, blades0: 70, bladesK: 6, ref, chordK: 0.9});
    if (hw.ipt) rows('ipt', 'ip', hw.ipt, hptRm * 1.05 - h45 / 2, hptRm * 1.1 - h45 / 2, hptRm * 1.05 + h45 / 2, hptRm * 1.1 + h45 / 2, lerp(s4.Tt, s45.Tt, 0.6), s45.Tt, Math.sqrt(s4.Pt * s45.Pt), s45.Pt, {turbine: true, blades0: 70, bladesK: 4, ref, chordK: 0.9});
    z -= 0.06 * ref;
    pt('lpt-in', z, hptRm * 1.05 - h45 / 2, hptRm * 1.05 + h45 / 2, s45, AX_MACH.lptIn, 1.33, family === 'turboprop' ? 'Power turbine inlet' : 'LP turbine inlet');
    const lptRm1 = fan ? Math.max(hptRm * 1.05, hptRm * (hw.lpt_growth ?? 1.35)) : hptRm * 1.08;
    const h5 = A5 / (2 * Math.PI * lptRm1);
    const nL = hw.lpt ?? (family === 'turboprop' ? hw.pt ?? 2 : 0);
    if (nL) rows(family === 'turboprop' ? 'pt' : 'lpt', family === 'turboprop' ? 'pt' : 'lp', nL, hptRm * 1.05 - h45 / 2, lptRm1 - h5 / 2, hptRm * 1.05 + h45 / 2, lptRm1 + h5 / 2, s45.Tt, s5.Tt, s45.Pt, s5.Pt, {turbine: true, blades0: 80, bladesK: 6, ref, chordK: 1.05});
    pt('lpt-exit', z, lptRm1 - h5 / 2, lptRm1 + h5 / 2, s5, AX_MACH.lptOut, 1.33, 'Turbine exit');
    // afterburner (turbojet with reheat): a jet pipe with spray rings and V-gutters
    const reheat = family === 'turbojet' && (input.afterburner_exit_temperature_K ?? 0) > 0;
    if (reheat) {
      const Lab = 1.6 * D;
      J.afterburner = {z0: z - 0.1 * D, z1: z - Lab, r: R * 0.98, T: input.afterburner_exit_temperature_K};
      z -= Lab;
    }
    // core nozzle: exit area from the solver's exit state, choked or not
    const A9 = Ac(s9, mh, Math.min(1, s9?.M ?? 1), 1.33);
    const zN = z - 0.12 * D;
    const plug = family === 'turbofan';
    // a turbofan's centre plug leaves the nozzle at about 72% of the turbine hub radius; the exit is the annulus round
    // it, sized to the solver's exit area, so the plug and the nozzle lip always leave the gap the gas needs
    const rPlug9 = plug ? (lptRm1 - h5 / 2) * 0.72 : 0;
    const rOut9 = Math.sqrt(A9 / Math.PI + rPlug9 ** 2);
    J.nozzle = {z0: z, z1: zN - (plug ? 0.25 * D : reheat ? 0.25 * D : 0.12 * D), rIn: lptRm1 + h5 / 2, rOut: rOut9, plugR: rPlug9, plug, reheat, A9, choked: out.nozzle_choked};
    pt('nozzle', J.nozzle.z1, rPlug9, rOut9, s9, Math.min(1, s9?.M ?? 1), 1.33, 'Core nozzle exit');
    // bypass duct and its nozzle
    if (fan) {
      const A19 = area(s19, mByp, Math.min(1, s19?.M ?? 0.9)) * k;
      J.splitR = coreTip * 1.12;
      const zB = hpc.z1 - 0.1 * D;
      const rIn19 = J.combustor.r1 * 1.25;
      J.bypass = {z0: J.splitZ, z1: zB, rOuter: R * 1.04, rSplit: J.splitR, rIn19, rOut19: Math.sqrt(A19 / Math.PI + rIn19 * rIn19), A19};
      pt('bypass-exit', zB, rIn19, J.bypass.rOut19, s19, Math.min(1, s19?.M ?? 0.9), 1.4, 'Bypass nozzle exit');
    }
    // the propeller and its reduction gearbox (turboprop)
    if (family === 'turboprop') {
      const prpm = input.propeller_rpm ?? 1200;
      J.spools.prop = {rpm: prpm, w: (prpm * 2 * Math.PI) / 60};
      J.prop = {D: input.propeller_diameter_m ?? 3, blades: hw.prop_blades ?? 6, z: 0.9 * D, ratio: (J.spools.pt?.rpm ?? 20000) / prpm};
      J.rgb = {z0: 0.75 * D, z1: 0.1 * D, r: 0.62 * D};
    }
    J.zEnd = J.nozzle.z1;
  } else if (family === 'ramjet') {
    // Axisymmetric, in the classic layout: a long double-cone spike at the front of a centre body that runs the
    // length of the engine, a short cowl round it, an annular burner between the centre body and the liner, and the
    // centre body's tail cone as the plug of the nozzle. Sizes follow the solver's flow areas, scaled so the burner
    // annulus fits the published-class diameter.
    const s0 = st(0);
    const s2 = st(2);
    const s3 = st(3);
    const s4 = st(4);
    const s9 = st(9);
    const half = (hw.spike_half_angle_deg ?? 22) * (Math.PI / 180);
    const half1 = half * 0.5;
    const rHub = R * 0.5;
    const rLiner = R * 0.92;
    const A3 = area(s3, mTot, s3?.M ?? 0.25);
    const k = (Math.PI * (rLiner * rLiner - rHub * rHub)) / A3;
    J.scale = k;
    // the spike: a slender first cone, then the solver's cone angle out to the centre body, ending just inside the lip
    const zCowl = 0.3 * D;
    const r1 = rHub * 0.5;
    const zShoulder = zCowl - 0.14 * D;
    const zKnee = zShoulder + (rHub - r1) / Math.tan(half);
    const zTip = zKnee + r1 / Math.tan(half1);
    const beta1 = obliqueBeta(J.mach, half1 * 0.8);
    // shock on lip: the cowl lip sits where the tip shock meets it, so the inlet swallows the whole captured stream
    const rLip = clamp((zTip - zCowl) * Math.tan(beta1), rHub * 1.35, R * 0.86);
    // behind the first shock the air turns again at the knee; that second shock is aimed at the lip as well
    const Mn1 = J.mach * Math.sin(beta1);
    const Mn2 = Math.sqrt((1 + 0.2 * Mn1 * Mn1) / Math.max(1e-3, 1.4 * Mn1 * Mn1 - 0.2));
    const M1 = Math.max(1.05, Mn2 / Math.sin(beta1 - half1 * 0.8));
    const beta2 = Math.atan2(rLip - r1, zKnee - zCowl);
    J.spike = {zTip, zKnee, zShoulder, zCowl, half, half1, r1, rMax: rHub, rLip, L: zTip - zShoulder};
    J.shock = {beta: beta1, beta2, M1};
    const spikeR = (z) => (z >= zKnee ? (zTip - z) * Math.tan(half1) : z >= zShoulder ? r1 + (zKnee - z) * Math.tan(half) : rHub);
    J.spikeR = spikeR;
    pt('inlet', zTip, 0, rLip, s0, J.mach, 1.4, 'Freestream');
    pt('cowl', zCowl, spikeR(zCowl), rLip, s2, Math.max(1, J.mach * 0.6), 1.4, 'Cowl lip');
    pt('diffuser', -0.62 * D, rHub, rLiner, s3, s3?.M ?? 0.25, 1.4, 'Burner inlet');
    J.combustor = {z0: -0.7 * D, z1: -1.95 * D, r0: rHub, r1: rLiner, T: s4.Tt, Tin: s3.Tt, gutters: hw.gutters ?? 2, nozzles: hw.fuel_nozzles ?? 16};
    pt('comb-exit', -1.95 * D, rHub, rLiner, s4, 0.4, 1.3, 'Burner exit');
    // the nozzle: the cowl closes down onto the tail cone; the throat is the annulus between the cowl's exit lip and
    // the plug, with the solver's throat area; the gas then expands round the rest of the plug in the open
    const zPlug0 = -2.0 * D;
    const zPlugTip = -3.05 * D;
    const zt = -2.42 * D;
    const plugR = (z) => (z >= zPlug0 ? rHub : z <= zPlugTip ? 0 : rHub * Math.pow((z - zPlugTip) / (zPlug0 - zPlugTip), 0.85));
    J.plugR = plugR;
    const At = area(s9, mTot * (1 + f), 1, 1.3) * k;
    const rp = plugR(zt);
    const rc = Math.min(R * 0.97, Math.sqrt(rp * rp + At / Math.PI));
    const A9 = area(s9, mTot * (1 + f), Math.max(1, s9?.M ?? 1), 1.3) * k;
    const rOut = Math.max(Math.sqrt(A9 / Math.PI), Math.sqrt(At / Math.PI));
    J.nozzle = {z0: -1.95 * D, zt, z1: zPlugTip, zPlug0, rIn: R, rT: rc, rp, rOut, choked: out.nozzle_choked};
    pt('throat', zt, rp, rc, s9, 1, 1.3, 'Nozzle throat');
    pt('nozzle', zPlugTip, 0, rOut, s9, s9?.M ?? 1, 1.3, 'Plug tip');
    J.zInlet = zTip;
    J.zEnd = zPlugTip;
  } else if (family === 'scramjet') {
    // two-dimensional: forebody ramps, cowl, isolator, a strut-injected combustor, a single expansion ramp
    const s0 = st(0);
    const s3 = st(3);
    const s4 = st(4);
    const s9 = st(9);
    const W = hw.width_m ?? 0.7;
    const A3 = area(s3, mTot, s3?.M ?? 2.2);
    J.scale = 1;
    const h3 = A3 / W;
    const ramp = (hw.ramp_angles_deg ?? [6, 6]).map((a) => (a * Math.PI) / 180);
    const Lf = hw.forebody_m ?? 3.0;
    J.scram = {W, h3: clamp(h3, 0.06, 0.4), ramp, Lf, Liso: hw.isolator_m ?? 0.6, Lc: hw.combustor_m ?? 1.0, Ln: hw.nozzle_m ?? 2.0, struts: hw.struts ?? 3, T: s4.Tt};
    const M0 = s0.M ?? input.mach;
    J.shocks = [];
    let Mloc = M0;
    for (const th of ramp) {
      const b = obliqueBeta(Mloc, th);
      J.shocks.push({theta: th, beta: b, M: Mloc});
      Mloc = Math.max(1.2, Mloc * 0.82);
    }
    // the flow path's walls: y_up is the vehicle's underside (the ramps, then the isolator and combustor roof, then
    // the expansion ramp), y_lo the captured stream's lower edge (the cowl inside, the shock or plume outside).
    // Capture height follows from continuity between freestream and combustor inlet (static density times speed).
    const rhoV = (s, M, g) => {
      const T = s.Tt / (1 + ((g - 1) / 2) * M * M);
      const p = s.Pt / Math.pow(1 + ((g - 1) / 2) * M * M, g / (g - 1));
      return (p / (R_AIR * T)) * M * Math.sqrt(g * R_AIR * T);
    };
    const M3 = s3?.M ?? 2.2;
    const CR = clamp(rhoV(s3, M3, 1.4) / rhoV(s0, M0, 1.4), 2, 20);
    const sc = J.scram;
    const [t1, t2] = ramp;
    const yU0 = -(Lf / 2) * Math.tan(t1) - (Lf / 2) * Math.tan(t1 + t2);
    const zC0 = -sc.Liso;
    const zC1 = -sc.Liso - sc.Lc;
    const zN1 = zC1 - sc.Ln;
    const div = (2 * Math.PI) / 180;
    const exp = (16 * Math.PI) / 180;
    sc.yU = (z) => (z >= Lf / 2 ? -(Lf - z) * Math.tan(t1) : z >= 0 ? -(Lf / 2) * Math.tan(t1) - (Lf / 2 - z) * Math.tan(t1 + t2) : z >= zC1 ? yU0 : yU0 + (zC1 - z) * Math.tan(exp));
    sc.yL = (z) => (z >= 0 ? sc.yU(z) - lerp(sc.h3, sc.h3 * CR, z / Lf) : z >= zC0 ? yU0 - sc.h3 : yU0 - sc.h3 - (zC0 - Math.max(z, zN1)) * Math.tan(div));
    sc.zC0 = zC0;
    sc.zC1 = zC1;
    sc.zN1 = zN1;
    sc.zCowlEnd = zC1 - 0.25 * sc.Ln;
    sc.CR = CR;
    const sp = (id, z, s, M, g, label) => pt(id, z, sc.yL(z), sc.yU(z), s, M, g, label);
    sp('inlet', Lf, s0, M0, 1.4, 'Freestream');
    sp('ramp2', Lf / 2, s0, Math.max(1.5, M0 * 0.85), 1.4, 'Second ramp');
    sp('cowl', 0, st(2), Mloc, 1.4, 'Cowl lip');
    sp('comb-in', zC0, s3, M3, 1.4, 'Combustor inlet');
    sp('comb-exit', zC1, s4, Math.max(1.1, M3 * 0.75), 1.3, 'Combustor exit');
    sp('nozzle', zN1, s9, s9?.M ?? 2.9, 1.3, 'Nozzle exit');
    J.zInlet = Lf;
    J.zEnd = -J.scram.Liso - J.scram.Lc - J.scram.Ln;
  }
  J.stations.sort((a, b) => b.z - a.z);
  J.D = D;
  J.R = R;
  J.length = J.zInlet - J.zEnd;

  // ---------------------------------------------------------------- swirl, from Euler's turbine equation
  // Each rotor does work cp*dTt per kilogram, which it puts in (compressor) or takes out of (turbine) the gas's
  // tangential velocity at the blade speed U: dVtheta = cp*dTt / U. Compressor gas swirls between a rotor and its
  // stator, which takes the swirl out again; turbine gas swirls between a nozzle guide vane and its rotor. The fan's
  // swirl lasts until the outlet guide vanes. Zero swirl entering each stage is assumed.
  const zones = {core: [], bypass: []};
  const spoolW = (name) => (name === 'fan' ? (J.spools.lp?.w ?? 0) / (hw.gear_ratio || 1) : J.spools[name]?.w ?? 0);
  for (const m of J.modules) {
    if (m.kind === 'fan') continue;
    const turbine = /t$/.test(m.kind);
    const cp = turbine ? 1150 : 1005;
    const dT = Math.abs((m.Tt1 ?? 0) - (m.Tt0 ?? 0)) / m.n;
    for (const s of m.stages) {
      const U = spoolW(m.spool) * (s.rh + s.rt) / 2;
      if (!U) continue;
      const vt = (cp * dT) / U;
      const [za, zb] = turbine ? [s.zs, s.zr] : [s.zr, s.zs];
      zones.core.push({z0: Math.max(za, zb), z1: Math.min(za, zb), vt});
    }
  }
  if (J.fan) {
    const s2 = stationOf(out, 2, 0);
    const s13 = stationOf(out, 13, 2);
    const U = spoolW('fan') * (J.fan.rh + J.fan.rt) / 2;
    const vt = U ? (1005 * (s13.Tt - s2.Tt)) / U : 0;
    const z = {z0: J.fan.zLE - J.fan.chord / 2, z1: J.ogv.z, vt};
    zones.core.push({...z, z1: J.splitZ, vt: vt * 0.6});
    zones.bypass.push(z);
  }
  /** tangential velocity at z on a stream: a smooth bump through each swirl zone */
  J.vtheta = (z, key = 'core') => {
    let v = 0;
    for (const zn of zones[key]) if (z <= zn.z0 && z >= zn.z1) v += zn.vt * Math.sin((Math.PI * (zn.z0 - z)) / (zn.z0 - zn.z1 || 1)) ** 0.5;
    return v;
  };
  // turbulence intensity (rms fluctuation over mean speed), typical values by region: a clean inlet, blade-row wakes,
  // the combustor's primary zone, the turbines, a free jet's shear layer
  J.tu = (z) => {
    if (J.combustor && z <= J.combustor.z0 && z >= J.combustor.z1) return 0.22;
    if (J.afterburner && z <= J.afterburner.z0 && z >= J.afterburner.z1) return 0.18;
    for (const m of J.modules) if (z <= m.z0 && z >= m.z1) return /t$/.test(m.kind) ? 0.08 : 0.05;
    if (J.nozzle && z < J.nozzle.z1) return 0.12;
    return 0.02;
  };

  // ---------------------------------------------------------------- time of flight along each stream, for the flow
  // particles: the speed between stations is interpolated, and t(z) = integral dz / V(z) is tabulated so a particle's
  // position is a pure function of time. The swirl angle is tabulated alongside: dtheta/dz = (Vtheta / r) / V.
  const tof = (sts, key = 'core') => {
    const zs = [];
    const ts = [];
    const ths = [];
    let th = 0;
    let t = 0;
    const N = 400;
    const zA = sts[0].z;
    const zB = sts[sts.length - 1].z;
    for (let i = 0; i <= N; i++) {
      const zz = lerp(zA, zB, i / N);
      if (i) {
        const st = J.at(zz, sts);
        const v = Math.max(20, st.V);
        const dz = Math.abs((zB - zA) / N);
        t += dz / v;
        th += (J.vtheta(zz, key) / Math.max(0.01 * D, (st.rh + st.rt) / 2)) * (dz / v);
      }
      zs.push(zz);
      ts.push(t);
      ths.push(th);
    }
    return {zs, ts, ths, T: t, thAt: (zz) => {
      const u = clamp(((zA - zz) / (zA - zB)) * N, 0, N);
      const i = Math.min(N - 1, Math.floor(u));
      return lerp(ths[i], ths[i + 1], u - i);
    }, zAt: (tt) => {
      tt = mod(tt, t);
      let lo = 0;
      let hi = N;
      while (hi - lo > 1) {
        const m = (lo + hi) >> 1;
        if (ts[m] < tt) lo = m;
        else hi = m;
      }
      return lerp(zs[lo], zs[hi], (tt - ts[lo]) / (ts[hi] - ts[lo] || 1));
    }};
  };
  /** the gas state at axial position z on a stream: radii, temperature and speed interpolated between stations */
  J.at = (zz, sts = J.coreStations) => {
    let i = 0;
    while (i < sts.length - 2 && sts[i + 1].z > zz) i++;
    const a = sts[i];
    const b = sts[i + 1];
    const t = clamp((a.z - zz) / (a.z - b.z || 1), 0, 1);
    return {rh: lerp(a.rh, b.rh, t), rt: lerp(a.rt, b.rt, t), Tt: lerp(a.Tt, b.Tt, t), T: lerp(a.T, b.T, t), V: lerp(a.V, b.V, t), Pt: a.Pt * Math.pow(b.Pt / a.Pt, t)};
  };
  J.coreStations = J.stations.filter((s) => s.id !== 'bypass-exit');
  J.paths.core = tof(J.coreStations);
  if (J.bypass) {
    const sFan = J.stations.find((s) => s.id === 'fan');
    const sB = J.stations.find((s) => s.id === 'bypass-exit');
    const inlet = J.stations.find((s) => s.id === 'inlet');
    const s13 = stationOf(out, 13, 2);
    const fb = flowAt(s13.Tt, AX_MACH.bypass, 1.4);
    const mid = {...sFan, z: J.splitZ - 0.05 * D, rh: J.splitR, rt: R, Tt: s13.Tt, Pt: s13.Pt, V: fb.V, T: fb.T};
    J.bypassStations = [inlet, {...sFan, rh: J.splitR * 0.9}, mid, sB];
    J.paths.bypass = tof(J.bypassStations, 'bypass');
  }
  return J;
}

/** oblique shock angle for a wedge of half-angle theta at Mach M (weak solution), by bisection on the theta-beta-M relation */
export function obliqueBeta(M, theta, g = 1.4) {
  const f = (b) => Math.atan((2 / Math.tan(b) * (M * M * Math.sin(b) ** 2 - 1)) / (M * M * (g + Math.cos(2 * b)) + 2)) - theta;
  let lo = Math.asin(1 / Math.max(1.0001, M)) + 1e-4;
  // the weak branch lies between the Mach angle and the angle of maximum deflection
  let hi = lo;
  let best = -1;
  for (let b = lo; b < Math.PI / 2; b += 0.002) {
    const v = f(b) + theta;
    if (v > best) {
      best = v;
      hi = b;
    }
  }
  if (best < theta) return hi;
  for (let k = 0; k < 60; k++) {
    const m = (lo + hi) / 2;
    if (f(m) > 0) hi = m;
    else lo = m;
  }
  return (lo + hi) / 2;
}

/** isentropic area ratio A/A* at Mach M */
export function areaRatio(M, g = 1.4) {
  return (1 / M) * Math.pow((2 / (g + 1)) * (1 + ((g - 1) / 2) * M * M), (g + 1) / (2 * (g - 1)));
}

/**
 * Work per kilogram each spool's compressor does (as a total-temperature rise, K). A compressor's work goes as its
 * blade speed squared (Euler: cp*dTt = U*dVtheta, with velocity triangles that scale with U), so when the cycle moves
 * off its design point a spool's speed scales as the square root of this work's ratio to design. Power turbines are
 * scaled by their own temperature drop.
 */
export function workOf(J) {
  const w = {};
  const add = (k, v) => (w[k] = (w[k] ?? 0) + Math.max(0, v));
  for (const m of J.modules) {
    if (m.kind === 'fan') continue;
    if (/t$/.test(m.kind)) {
      if (m.spool === 'pt') add('pt', (m.Tt0 ?? 0) - (m.Tt1 ?? 0));
      continue;
    }
    add(m.spool, (m.Tt1 ?? 0) - (m.Tt0 ?? 0));
  }
  if (J.fan) {
    const s2 = J.stations.find((x) => x.id === 'fan');
    add('lp', (J.fan.Tt13 ?? 0) - (s2?.Tt ?? 0));
  }
  return w;
}

/** scale every spool's speed from design by sqrt(work / design work), held between 55 % and 115 % */
export function scaleSpools(J, design) {
  const w = workOf(J);
  J.speedRatio = {};
  for (const [k, sp] of Object.entries(J.spools)) {
    if (k === 'prop' || !(design[k] > 0) || !(w[k] > 0)) continue;
    const r = Math.min(1.15, Math.max(0.55, Math.sqrt(w[k] / design[k])));
    sp.rpm *= r;
    sp.w *= r;
    J.speedRatio[k] = r;
  }
  if (J.prop && J.spools.pt && J.spools.prop) J.prop.ratio = J.spools.pt.rpm / J.spools.prop.rpm;
}

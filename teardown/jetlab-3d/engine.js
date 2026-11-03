// The engine built from code, sized from one makeJet() layout: blade rows lofted from cambered airfoils on the radii
// the cycle solve gives, discs and drums under them, casings with bolted flanges, the combustor with its fuel
// nozzles and a flame at the turbine-inlet temperature's black-body colour, shafts and bearings, gearboxes, the
// nacelle, the external dress (fuel manifold, bleed ducts, harness, accessory gearbox and its units), a display stand,
// and the gas itself as particles moving at the solver's station speeds, coloured by temperature.
//
// update(t) poses everything for simulated time t (seconds): each spool turns at its own published speed, so the
// gearbox and every rotor agree; the particles' positions are a pure function of t.
import * as THREE from 'three';
import {blackbody, bladeGeometry, boltGeometry, glowIntensity, instances, makeMaterials, mergeAll, revolve, ringOf, roundedBox} from './detail.js';
import {mod, obliqueBeta} from './kin.js';
import {alloy} from '../shared/alloys.js';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

const V3 = THREE.Vector3;
const TAU = Math.PI * 2;
export const ACCENT = '#e8923e';

export const LAYERS = [
  {id: 'nacelle', name: 'Nacelle and cowls'},
  {id: 'casing', name: 'Casings and frames'},
  {id: 'rotor', name: 'Rotors and blades'},
  {id: 'stator', name: 'Stators and vanes'},
  {id: 'combustor', name: 'Combustor and flame'},
  {id: 'shaft', name: 'Shafts and bearings'},
  {id: 'gearbox', name: 'Gearboxes'},
  {id: 'dress', name: 'Pipes, harness and accessories'},
  {id: 'flow', name: 'Gas flow'},
  {id: 'shock', name: 'Shocks (schlieren)'},
  {id: 'stand', name: 'Display stand'},
];

/** a flame's emissive strength: the T^4 law above the Draper point, compressed logarithmically for the screen */
const flameI = (T) => 0.35 + 0.35 * Math.log10(1 + glowIntensity(T, 1300));
const phys = (o) => new THREE.MeshPhysicalMaterial({envMapIntensity: 1, ...o});
const gearGeo = (R, n, t, tooth = 0.1) => {
  const s = new THREE.Shape();
  const k = 4 * n;
  for (let i = 0; i <= k; i++) {
    const a = (i / k) * TAU;
    const r = i % 4 < 2 ? R : R * (1 - tooth);
    i ? s.lineTo(r * Math.sin(a), r * Math.cos(a)) : s.moveTo(r * Math.sin(a), r * Math.cos(a));
  }
  const h = new THREE.Path();
  h.absarc(0, 0, R * 0.3, 0, TAU, true);
  s.holes.push(h);
  return new THREE.ExtrudeGeometry(s, {depth: t, bevelEnabled: false, curveSegments: 3}).translate(0, 0, -t / 2);
};
const tube = (pts, r, closed = false, seg = 64) => new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, closed, 'centripetal'), seg, r, 10, closed);

export function buildEngine(J) {
  const D = J.D;
  const R = J.R;
  const hw = J.hw;
  const fam = J.family;
  const root = new THREE.Group();
  const movers = [];
  const cutMats = new Set();
  const hot = [];
  const M = makeMaterials({});
  // The cut is made in the geometry, not with clipping planes, so every pass (ambient occlusion, shadows, glow) sees
  // the same model. Static parts are built over the kept arc only; rotating parts stay whole, as in a museum cutaway.
  // Angles run about the axis from +x toward +y; the cutaway drops the quadrant facing the camera (x > 0, y > 0).
  const CUT = J.cut ?? 'cutaway';
  const KEEP = CUT === 'solid' ? null : CUT === 'half' || fam === 'scramjet' ? [Math.PI / 2, Math.PI] : [Math.PI / 2, 1.5 * Math.PI];
  const keep = (a) => !KEEP || mod(a - KEEP[0], TAU) <= KEEP[1] + 1e-9;
  // lathe's own angle starts a quarter turn behind ours once it is turned onto the engine axis
  // model detail (1 full, 0.5 for the lowest quality tier): lathe segments, blade sections, flow tracers
  const DET = J.detail ?? 1;
  const segs = (n) => Math.max(24, Math.round(n * DET));
  const lc = (pts, seg0 = 128) => {
    const seg = segs(seg0);
    const g = KEEP ? revolve(pts, seg, KEEP[0] + Math.PI / 2, KEEP[1]) : revolve(pts, seg);
    g.userData.profile = pts;
    return g;
  };
  const torusC = (r, tr, ts = 8, n = 128) => {
    const g = new THREE.TorusGeometry(r, tr, ts, n, KEEP ? KEEP[1] : TAU);
    if (KEEP) g.rotateZ(KEEP[0]);
    return g;
  };

  // ------------------------------------------------------------ materials
  const cut = (m) => {
    m.userData.cut = true;
    m.side = THREE.DoubleSide;
    cutMats.add(m);
    return m;
  };
  const castTex = M.alu.roughnessMap;
  // Materials come from the shared alloy library (teardown/shared/alloys.js): each part names a real alloy or coating
  // and gets its reflectance, roughness, anisotropy, coating and surface detail. repeat sets how the detail tiles over
  // the part's UVs (round x along, for lathe-made parts).
  const DS = THREE.DoubleSide;
  const mat = {
    titanium: alloy('ti64', {repeat: [1, 5], side: DS}),
    composite: alloy('cfrp', {repeat: [3, 9], side: DS}),
    aluminium: alloy('alMachined', {repeat: [1, 5], side: DS}),
    blade: alloy('ti64', {repeat: [1, 3], side: DS}),
    stator: alloy('steel', {repeat: [1, 3], side: DS}),
    hotBlade: alloy('inconel718', {repeat: [1, 3], side: DS}),
    tbc: alloy('cmsxFilm', {repeat: [1, 1], side: DS}),
    disc: cut(alloy('inconel718', {repeat: [1, 2]})),
    coldCase: cut(alloy('alCast', {repeat: [24, 3]})),
    hotCase: cut(alloy('stainlessHot', {repeat: [24, 3]})),
    inlet: cut(alloy('ti64', {repeat: [24, 3]})),
    nacelle: cut(alloy('paintWhite', {repeat: [40, 10]})),
    liner: cut(alloy('cmc', {repeat: [24, 3]})),
    spinner: alloy('paintBlack', {repeat: [8, 4], side: DS}),
    shaft: alloy('steel', {repeat: [1, 6]}),
    drum: cut(alloy('ti64', {repeat: [1, 6]})),
    hotDrum: cut(alloy('inconel718', {repeat: [1, 6]})),
    combLiner: cut(alloy('tbcEffusion', {repeat: [120, 10]})),
    coolPanel: alloy('coolPanel', {repeat: [1, 6]}),
    stand: alloy('paintGrey', {repeat: [2, 2]}),
    pipe: alloy('steel', {repeat: [1, 8]}),
    braid: phys({color: '#9aa0a7', metalness: 0.8, roughness: 0.55}),
    harness: phys({color: '#3b3f2f', metalness: 0, roughness: 0.75, sheen: 0.4, sheenColor: '#5b604a'}),
    plastic: phys({color: '#2a2d31', metalness: 0.05, roughness: 0.45}),
    box: alloy('alCast', {repeat: [2, 2]}),
    gear: alloy('steel', {repeat: [1, 2]}),
    inconel: cut(alloy('inconel718', {repeat: [24, 3]})),
    tps: cut(alloy('cmc', {repeat: [6, 30]})),
    abradable: cut(alloy('honeycomb', {repeat: [60, 1]})),
    acoustic: cut(alloy('acoustic', {repeat: [90, 2]})),
    bearing: alloy('bearing'),
    shock: null,
  };

  // Service-state inputs: which materials are erodible blades, and how hot each hot material runs (from the solve).
  // Hot parts take a heat tint whose colour follows this temperature, and soot first where it is highest.
  for (const k of ['titanium', 'aluminium', 'blade', 'stator']) mat[k].userData.blade = true;
  {
    const Tst = (id) => J.stations.find((x) => x.id === id)?.Tt;
    const T4 = J.combustor?.T ?? Math.max(...J.stations.map((x) => x.Tt));
    const T45 = Tst('lpt-in') ?? T4 * 0.8;
    const T5 = Tst('lpt-exit') ?? T45 * 0.85;
    // metal runs below the gas it sits in: cooled turbine parts well below, uncooled casings and nozzles closer
    mat.tbc.userData.T = T4 - 250;
    mat.hotBlade.userData.T = T45 - 150;
    mat.hotCase.userData.T = fam === 'ramjet' || fam === 'scramjet' ? T4 - 400 : (T45 + T5) / 2 - 150;
    mat.inconel.userData.T = T5 - 80;
    mat.hotDrum.userData.T = T45 - 350;
    mat.disc.userData.T = T45 - 400;
    mat.combLiner.userData.T = T4 - 300;
    mat.tps.userData.T = T4 - 600;
    mat.coolPanel.userData.T = T4 - 900;
  }
  const fanMat = mat[hw.fan_material] ?? mat.titanium;
  const boltGeo = boltGeometry(Math.max(0.045, 0.05 * D));
  const smallBolt = boltGeometry(Math.max(0.03, 0.03 * D));

  // ------------------------------------------------------------ fire
  // Burning gas as an additive shader. Its colour runs along a temperature profile through the flame (a 1D ramp of
  // black-body colours, brightness from the T^4 law compressed for the screen); turbulence is 3D value noise carried
  // downstream at the gas's own speed, so the flicker moves with the flow and freezes when the clock stops; faces seen
  // edge-on fade, so the volume reads as gas and not as a shell. An exhaust plume adds Mach diamonds: bright bands where
  // the shock cells recompress the jet, spaced by Pack's formula from the fully expanded jet Mach number.
  const flames = [];
  /** a free jet from a nozzle exit: a slowly spreading column, cooling along its length, with Mach diamonds */
  const plume = (g, z0, r0, T0, V, P, strength) => {
    const L = Math.max(6 * r0, P.spacing ? 5 * P.spacing : 0);
    const pts = [];
    for (let i = 0; i <= 30; i++) {
      const u = i / 30;
      pts.push([r0 * (0.98 + 0.5 * u) * (1 - 0.92 * u ** 4) + 0.001, z0 - u * L]);
    }
    const m = flameMat((u) => T0 - (T0 - 700) * u ** 1.4, z0, z0 - L, V, strength, P.spacing ? {spacing: P.spacing, n: 3} : null);
    addFlame(g, lc([[0.001, z0], ...pts, [0.001, z0 - L]], 96), m, 'plume');
  };
  const rampTex = (Tof, rgb = null) => {
    const N = 96;
    const data = new Float32Array(N * 4);
    const c = new THREE.Color();
    for (let i = 0; i < N; i++) {
      if (rgb) {
        data.set([...rgb(i / (N - 1)), 1], i * 4);
        continue;
      }
      const T = Tof(i / (N - 1));
      blackbody(Math.max(900, T), c);
      const k = T < 900 ? 0 : 0.25 + 0.4 * Math.log10(1 + glowIntensity(T, 1300));
      data.set([c.r * k, c.g * k, c.b * k, 1], i * 4);
    }
    const t = new THREE.DataTexture(data, N, 1, THREE.RGBAFormat, THREE.FloatType);
    t.magFilter = t.minFilter = THREE.LinearFilter;
    t.needsUpdate = true;
    return t;
  };
  const FLAME_VS = `varying vec3 vL; varying vec3 vN; varying vec3 vV;
    void main() { vL = position; vec4 w = modelMatrix * vec4(position, 1.0); vN = normalize(mat3(modelMatrix) * normal);
      vV = cameraPosition - w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
  const FLAME_FS = `uniform sampler2D uRamp; uniform float uT, uZ0, uZ1, uV, uK, uS, uCell, uCells, uG;
    varying vec3 vL; varying vec3 vN; varying vec3 vV;
    float h3(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
    float vn(vec3 x) { vec3 i = floor(x); vec3 f = fract(x); f = f * f * (3.0 - 2.0 * f);
      return mix(mix(mix(h3(i), h3(i + vec3(1, 0, 0)), f.x), mix(h3(i + vec3(0, 1, 0)), h3(i + vec3(1, 1, 0)), f.x), f.y),
                 mix(mix(h3(i + vec3(0, 0, 1)), h3(i + vec3(1, 0, 1)), f.x), mix(h3(i + vec3(0, 1, 1)), h3(i + vec3(1, 1, 1)), f.x), f.y), f.z); }
    float fbm(vec3 p) { float a = 0.5; float s = 0.0; for (int i = 0; i < 4; i++) { s += a * vn(p); p = p * 2.03 + 7.1; a *= 0.5; } return s; }
    void main() {
      float u = clamp((uZ0 - vL.z) / (uZ0 - uZ1), 0.0, 1.0);
      vec3 q = vec3(vL.x, vL.y, vL.z + uT * uV) / uK;
      float n = fbm(q);
      float edge = abs(dot(normalize(vN), normalize(vV)));
      float a = uS * pow(edge, 1.3) * (0.25 + 1.3 * n * n) * smoothstep(0.0, 0.06, u) * (1.0 - smoothstep(0.82, 1.0, u));
      if (uCells > 0.5) {
        float d = max(0.0, (uZ0 - vL.z) / uCell);
        float band = pow(0.5 + 0.5 * cos(6.2831853 * d), 8.0);
        a *= (0.35 + 2.2 * band * exp(-d / uCells));
      }
      gl_FragColor = vec4(texture2D(uRamp, vec2(u, 0.5)).rgb * a * uG, 1.0);
    }`;
  /** a flame material: Tof(u) is the gas temperature from the flame's start (u = 0, at z0) to its end (u = 1, z1) */
  const flameMat = (Tof, z0, z1, V, strength = 1, cells = null, rgb = null) => {
    const m = new THREE.ShaderMaterial({
      uniforms: {uRamp: {value: rampTex(Tof, rgb)}, uT: {value: 0}, uZ0: {value: z0}, uZ1: {value: z1}, uV: {value: V}, uK: {value: 0.07 * D}, uS: {value: strength},
        uCell: {value: cells?.spacing ?? 1}, uCells: {value: cells ? cells.n : 0}, uG: {value: 1}},
      vertexShader: FLAME_VS,
      fragmentShader: FLAME_FS,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    });
    flames.push(m);
    return m;
  };
  /** add a flame mesh; it is drawn in the main pass and again in the glow pass, so the bloom follows its flicker */
  const addFlame = (g, geo, m, id = 'flame') => {
    const f = add(g, mesh(geo, m), id);
    f.userData.spark = true;
    f.renderOrder = 5;
    hot.push(f);
    return f;
  };
  /** the fully expanded jet Mach number from the nozzle pressure ratio, and the shock-cell spacing (Pack's formula) */
  const plumeOf = (Pt9, d9, g = 1.3) => {
    const s0 = J.stations[0];
    const Ps0 = s0.Pt / Math.pow(1 + 0.2 * J.mach * J.mach, 3.5);
    const npr = Pt9 / Ps0;
    const Mj = Math.sqrt(Math.max(0, (2 / (g - 1)) * (Math.pow(npr, (g - 1) / g) - 1)));
    return {npr, Mj, spacing: Mj > 1.02 ? 1.306 * d9 * Math.sqrt(Mj * Mj - 1) : 0};
  };

  // ------------------------------------------------------------ physics overlays: shocks, blade modes, rotor blur
  // A shock seen in a schlieren image is a line whose darkness follows the density gradient. Here each shock surface
  // is shaded by the density jump across it (the Rankine-Hugoniot ratio for its normal Mach number), brightest where
  // it is seen edge-on, so it reads as a sharp line in a side view and as a faint sheet face-on.
  const rhoJump = (Mn, g = 1.4) => (Mn <= 1 ? 1 : ((g + 1) * Mn * Mn) / ((g - 1) * Mn * Mn + 2));
  const schlieren = (jump) => new THREE.ShaderMaterial({
    uniforms: {uK: {value: Math.min(1, (jump - 1) / 1.5)}},
    vertexShader: 'varying vec3 vN; varying vec3 vV; void main() { vec4 w = modelMatrix * vec4(position, 1.0); vN = normalize(mat3(modelMatrix) * normal); vV = cameraPosition - w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }',
    fragmentShader: 'uniform float uK; varying vec3 vN; varying vec3 vV; void main() { float e = 1.0 - abs(dot(normalize(vN), normalize(vV))); float a = uK * (0.06 + 0.9 * pow(e, 6.0)); gl_FragColor = vec4(vec3(0.82, 0.88, 0.96) * a, 1.0); }',
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
  });
  // first bending and first torsion of the rotor blades, as an animated overlay (amplitude exaggerated by a slider)
  const vib = {uMode: {value: 0}, uAmp: {value: 0}, uVT: {value: 0}};
  const addVib = (m) => {
    if (m.userData.vib) return m;
    m.userData.vib = true;
    const prev = m.onBeforeCompile;
    const prevKey = m.customProgramCacheKey?.call(m) ?? '';
    m.onBeforeCompile = (sh, r) => {
      if (prev) prev.call(m, sh, r);
      Object.assign(sh.uniforms, vib);
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nuniform float uMode, uAmp, uVT; attribute float aVib; attribute float aMid;').replace('#include <begin_vertex>', `#include <begin_vertex>
        if (uMode > 0.5 && aVib > 0.5) {
          float sp = uv.y;
          float ph = sin(uVT * 6.2831853);
          if (uMode < 1.5) transformed.x += uAmp * sp * sp * ph;
          else {
            float a = (uAmp * 4.0) * sp * ph;
            float dz = transformed.z - aMid;
            transformed.xz = vec2(transformed.x * cos(a) - dz * sin(a), transformed.x * sin(a) + dz * cos(a) + aMid);
          }
        }`);
    };
    m.customProgramCacheKey = () => `vib|${prevKey}`;
    return m;
  };
  /** mark a blade geometry as vibrating, with its section centre (for torsion) */
  const vibGeo = (geo, zMid) => {
    const n = geo.attributes.position.count;
    geo.setAttribute('aVib', new THREE.Float32BufferAttribute(new Float32Array(n).fill(1), 1));
    geo.setAttribute('aMid', new THREE.Float32BufferAttribute(new Float32Array(n).fill(zMid), 1));
    return geo;
  };
  // Rotor blur, from each row's real angular speed at the chosen playback rate. Once a row turns more than about
  // one and a half blade pitches per frame the eye (and a camera at a normal shutter speed) sees a smeared,
  // translucent disc instead of blades: the sharp blades give way to a lit annulus whose opacity is the row's
  // solidity, the fraction of the annulus its blades cover. Between a third of a pitch and 1.5 pitches the two blend.
  const blurs = [];
  const blurDisc = (g, rh, rt, z, w, n, spool, color, row = null, chord = 0) => {
    const m = new THREE.MeshStandardMaterial({color, metalness: 0.7, roughness: 0.45, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide});
    const d = mesh(revolve([[rh, z], [rt, z]], 128), m);
    d.visible = false;
    d.renderOrder = 4;
    g.add(d);
    const solidity = Math.min(0.9, Math.max(0.35, (chord * n) / (Math.PI * (rh + rt))));
    blurs.push({d, m, n, spool, row, solidity});
  };

  // ------------------------------------------------------------ groups: one per layer and module, so the explode
  // pulls whole modules apart along the axis
  const layer = {};
  for (const L of LAYERS) {
    layer[L.id] = new THREE.Group();
    root.add(layer[L.id]);
  }
  const explodable = [];
  const radialRows = [];
  const groups = new Map();
  const grp = (lay, key, v = new V3()) => {
    const id = `${lay}/${key}`;
    if (!groups.has(id)) {
      const g = new THREE.Group();
      layer[lay].add(g);
      explodable.push({g, v});
      groups.set(id, g);
    }
    return groups.get(id);
  };
  const part = (obj, id, meta = {}) => {
    obj.userData.pick = {id, meta};
    return obj;
  };
  const add = (g, obj, id, meta) => {
    g.add(id ? part(obj, id, meta) : obj);
    return obj;
  };
  const mesh = (geo, m) => new THREE.Mesh(geo, m);
  /** a ring of bolts on a flange face at radius r and axial position z, heads facing dir (+1 front, -1 rear) */
  const boltRing = (g, r, z, n, dir = 1, geo = boltGeo, whole = false) => {
    const items = [];
    for (let k = 0; k < n; k++) {
      const a = (k / n) * TAU;
      if (!whole && !keep(a)) continue;
      items.push([new V3(r * Math.cos(a), r * Math.sin(a), z), new V3(0, 0, dir)]);
    }
    const m = instances(geo, M.bolt, items);
    m.frustumCulled = false;
    g.add(m);
    return m;
  };
  /** a casing wall from z0 to z1 between inner radius ri(z) and thickness t, with a bolted flange at each end */
  const casing = (g, id, z0, z1, r0, r1, t, m, opts = {}) => {
    const n = opts.seg ?? 16;
    const inner = [];
    // a smooth blend between the end radii (zero slope at each flange), not a straight cone
    for (let i = 0; i <= n; i++) {
      const u = i / n;
      inner.push([r0 + (r1 - r0) * u * u * (3 - 2 * u), z0 + (z1 - z0) * u]);
    }
    const outer = inner.map(([r, z]) => [r + t, z]).reverse();
    const geo = lc([...inner, ...outer, inner[0]], 96);
    add(g, mesh(geo, m), id, opts.meta);
    for (const [r, z, dir] of opts.flanges === false ? [] : [[r0, z0, 1], [r1, z1, -1]]) {
      const fh = Math.max(0.025 * D, 3 * t);
      const fw = Math.max(0.012 * D, 1.2 * t);
      const fz = dir > 0 ? z - fw : z;
      add(g, mesh(lc([[r + t, fz], [r + t + fh, fz], [r + t + fh, fz + fw], [r + t, fz + fw], [r + t, fz]], 96), m), id, opts.meta);
      boltRing(g, r + t + fh * 0.6, dir > 0 ? fz : fz + fw, Math.max(24, Math.round((TAU * r) / (0.035 * D))), dir > 0 ? -1 : 1, smallBolt);
    }
  };
  const spinT = {};
  const spool = (name) => {
    if (!spinT[name]) {
      const sp = J.spools[name] ?? J.spools.hp ?? {w: 0};
      spinT[name] = {w: sp.w, objs: []};
    }
    return spinT[name];
  };
  const spins = (obj, name, sign = 1) => {
    spool(name).objs.push([obj, sign]);
    return obj;
  };

  // ------------------------------------------------------------ blade rows
  const modOff = {fan: 0.7, lpc: 0.45, ipc: 0.25, hpc: 0.05, compressor: 0.05, comb: -0.25, hpt: -0.55, ipt: -0.7, lpt: -0.9, pt: -0.9, nozzle: -1.25, ab: -1.2};
  const ex = (key) => new V3(0, 0, (modOff[key] ?? 0) * D);
  const rotorRow = (g, st, kind, matR, spoolName, opts = {}) => {
    const turbine = !!opts.turbine;
    const h = st.rt - st.rh;
    const geo = bladeGeometry({
      rh: st.rh * 0.995,
      rt: st.rt - 0.006 * h - 0.0015 * D,
      chordH: st.chord * (opts.chordH ?? 1),
      chordT: st.chord * (opts.chordT ?? 0.95),
      stagH: ((turbine ? 25 : 32) * Math.PI) / 180,
      stagT: ((turbine ? 42 : 56) * Math.PI) / 180,
      camber: turbine ? 0.17 : 0.06,
      thick: turbine ? 0.14 : 0.06,
      nr: Math.max(4, Math.round(8 * DET)),
      nc: Math.max(7, Math.round(13 * DET)),
      flip: turbine ? -1 : 1,
    });
    geo.translate(0, 0, st.zr);
    vibGeo(geo, st.zr);
    addVib(matR);
    const row = ringOf(geo, matR, Math.max(8, st.blades));
    blurDisc(g, st.rh, st.rt, st.zr, 0, Math.max(8, st.blades), spoolName, matR.color.clone().multiplyScalar(0.8), row, st.chord);
    row.castShadow = true;
    add(g, row, opts.id ?? kind, {stage: st.i + 1, module: kind});
    spins(row, spoolName);
    // Each blade stands on a platform; the platforms of a row nearly close into a ring, with small gaps between them.
    // Below the platform a shank and the root: an axial dovetail on a compressor blade, a three-lobe fir tree on a
    // turbine blade, sized to fill the rim of the disc (which stops at 0.93 of the hub radius). The row lifts
    // radially out of its slots in the exploded view, so the roots show.
    {
      const nB = Math.max(8, st.blades);
      const pw = ((2 * Math.PI * st.rh) / nB) * 0.965;
      const ax = st.chord * (turbine ? 0.9 : 0.8);
      const tp = Math.max(0.0025 * D, 0.06 * h);
      const r1 = st.rh - tp;
      const r0 = st.rh * 0.93;
      const plat = new THREE.BoxGeometry(pw, tp, ax).translate(0, st.rh - tp / 2, st.zr);
      const rs = new THREE.Shape();
      const w = pw * 0.36;
      if (turbine) {
        // fir tree: three pairs of lobes, narrowing toward the bottom
        const L = r1 - r0;
        rs.moveTo(-w * 0.55, 0);
        for (let k = 0; k < 3; k++) {
          const y0 = -(k * L) / 3;
          const ww = w * (1 - 0.18 * k);
          rs.lineTo(-ww, y0 - L * 0.08);
          rs.lineTo(-ww * 0.62, y0 - L * 0.24);
          rs.lineTo(-ww * 0.82, y0 - L * 0.33);
        }
        rs.lineTo(-w * 0.3, -L);
        rs.lineTo(w * 0.3, -L);
        for (let k = 2; k >= 0; k--) {
          const y0 = -(k * L) / 3;
          const ww = w * (1 - 0.18 * k);
          rs.lineTo(ww * 0.82, y0 - L * 0.33);
          rs.lineTo(ww * 0.62, y0 - L * 0.24);
          rs.lineTo(ww, y0 - L * 0.08);
        }
        rs.lineTo(w * 0.55, 0);
      } else {
        // dovetail: a neck flaring out into the slot
        const L = r1 - r0;
        rs.moveTo(-w * 0.45, 0);
        rs.lineTo(-w * 0.4, -L * 0.45);
        rs.lineTo(-w * 0.85, -L);
        rs.lineTo(w * 0.85, -L);
        rs.lineTo(w * 0.4, -L * 0.45);
        rs.lineTo(w * 0.45, 0);
      }
      rs.closePath();
      const root = new THREE.ExtrudeGeometry(rs, {depth: ax * 0.85, bevelEnabled: false}).translate(0, r1, st.zr - (ax * 0.85) / 2);
      const pr = ringOf(mergeAll([plat, root]), matR, nB);
      add(g, pr, opts.id ?? kind, {stage: st.i + 1, module: kind});
      spins(pr, spoolName);
      radialRows.push({m: row, n: nB}, {m: pr, n: nB});
    }
    if (turbine && opts.shroud) {
      // interlocking tip shrouds form a ring, with two knife-edge seal fins running in the honeycomb liner
      const c = st.chord * 0.62;
      const r0 = st.rt - 0.004 * D;
      const prof = [[r0, st.zr + c / 2], [r0 + 0.006 * D, st.zr + c / 2], [r0 + 0.006 * D, st.zr + c * 0.25], [r0 + 0.016 * D, st.zr + c * 0.2], [r0 + 0.006 * D, st.zr + c * 0.12], [r0 + 0.006 * D, st.zr - c * 0.12], [r0 + 0.016 * D, st.zr - c * 0.2], [r0 + 0.006 * D, st.zr - c * 0.25], [r0 + 0.006 * D, st.zr - c / 2], [r0, st.zr - c / 2], [r0, st.zr + c / 2]];
      const sh = add(g, mesh(revolve(prof, 128), matR), opts.id ?? kind, {stage: st.i + 1, module: kind});
      spins(sh, spoolName);
      radialRows.push({m: sh, ring: true, r: r0});
    }
    return row;
  };
  const statorRow = (g, st, kind, matS, opts = {}) => {
    const turbine = !!opts.turbine;
    const h = st.rt - st.rh;
    const geo = bladeGeometry({
      rh: st.rh - 0.002 * D,
      rt: st.rt + 0.004 * D,
      chordH: st.chord * 0.85,
      chordT: st.chord * 0.9,
      stagH: ((turbine ? 55 : 22) * Math.PI) / 180,
      stagT: ((turbine ? 52 : 30) * Math.PI) / 180,
      camber: turbine ? 0.2 : 0.07,
      thick: turbine ? 0.16 : 0.06,
      nr: Math.max(3, Math.round(5 * DET)),
      nc: Math.max(7, Math.round(11 * DET)),
      flip: turbine ? 1 : -1,
    });
    geo.translate(0, 0, st.zs);
    const n = Math.max(8, Math.round(st.blades * (turbine ? 0.55 : 1.25)));
    const row = ringOf(geo, matS, n, 0.13, keep);
    add(g, row, opts.id ?? (turbine ? 'ngv' : 'stator'), {stage: st.i + 1, module: kind});
    // the inner shroud (vane platforms joined into a band) with a honeycomb seal land under it, facing knife-edge
    // seal teeth on the drum; and, for turbine vanes, an outer platform band against the case
    const ax = st.chord * 0.8;
    const tb = Math.max(0.003 * D, 0.05 * h);
    const band = lc([[st.rh - 0.002 * D - tb, st.zs + ax / 2], [st.rh - 0.002 * D, st.zs + ax / 2], [st.rh - 0.002 * D, st.zs - ax / 2], [st.rh - 0.002 * D - tb, st.zs - ax / 2], [st.rh - 0.002 * D - tb, st.zs + ax / 2]], 128);
    add(g, mesh(band, matS), opts.id ?? (turbine ? 'ngv' : 'stator'), {stage: st.i + 1, module: kind});
    add(g, mesh(lc([[st.rh - 0.002 * D - tb - 0.004 * D, st.zs + ax * 0.4], [st.rh - 0.002 * D - tb, st.zs + ax * 0.4], [st.rh - 0.002 * D - tb, st.zs - ax * 0.4], [st.rh - 0.002 * D - tb - 0.004 * D, st.zs - ax * 0.4]], 128), mat.abradable), 'seal', {stage: st.i + 1, module: kind});
    if (turbine) add(g, mesh(lc([[st.rt + 0.004 * D, st.zs + ax / 2], [st.rt + 0.004 * D + tb, st.zs + ax / 2], [st.rt + 0.004 * D + tb, st.zs - ax / 2], [st.rt + 0.004 * D, st.zs - ax / 2], [st.rt + 0.004 * D, st.zs + ax / 2]], 128), matS), 'ngv', {stage: st.i + 1, module: kind});
    st.sealR = st.rh - 0.002 * D - tb - 0.004 * D;
    void h;
    return row;
  };
  /** the rotor drum or discs under a module's rows: a drum following the hub line, a disc per stage below it */
  const discs = (g, m, matD, spoolName, bore) => {
    const pts = [];
    pts.push([m.stages[0].rh * 0.98, m.z0 + 0.01 * D]);
    for (const s of m.stages) pts.push([s.rh * 0.985, s.z]);
    pts.push([m.stages[m.stages.length - 1].rh * 0.98, m.z1 - 0.005 * D]);
    const drumIn = pts.map(([r, z]) => [r * 0.94, z]).reverse();
    const drum = add(g, mesh(revolve([...pts, ...drumIn, pts[0]], 128), matD), m.kind, {module: m.kind});
    spins(drum, spoolName);
    for (const s of m.stages) {
      if (s.sealR == null) continue;
      const tooth = (zz) => [[s.rh * 0.94, zz + 0.006 * D], [s.sealR - 0.0008 * D, zz + 0.0006 * D], [s.sealR - 0.0008 * D, zz - 0.0006 * D], [s.rh * 0.94, zz - 0.006 * D]];
      const ax = s.chord * 0.25;
      // the three teeth of a stage as one mesh (one draw call, not three)
      const teeth = mergeGeometries([s.zs + ax, s.zs, s.zs - ax].map((zz) => revolve(tooth(zz), segs(128))));
      spins(add(g, mesh(teeth, matD), 'seal', {module: m.kind}), spoolName);
    }
    for (const s of m.stages) {
      const w = s.chord * 0.35;
      const prof = [[s.rh * 0.93, s.zr + w], [bore * 1.6, s.zr + w * 0.35], [bore, s.zr + w * 0.5], [bore, s.zr - w * 0.5], [bore * 1.6, s.zr - w * 0.35], [s.rh * 0.93, s.zr - w], [s.rh * 0.93, s.zr + w]];
      const d = add(g, mesh(revolve(prof, 128), matD), 'disc', {module: m.kind, stage: s.i + 1});
      spins(d, spoolName);
    }
  };
  const MOD_NAME = {lpc: 'booster', ipc: 'ipc', hpc: 'hpc', compressor: 'compressor', hpt: 'hpt', ipt: 'ipt', lpt: 'lpt', pt: 'pt'};
  const shaftR = {lp: 0.035 * D, ip: 0.055 * D, hp: 0.075 * D, pt: 0.035 * D};
  if (fam === 'turbojet' || fam === 'turboprop') shaftR.hp = 0.06 * D;
  for (const m of J.modules) {
    if (m.kind === 'fan') continue;
    const turbine = /t$/.test(m.kind) && m.kind !== 'hpc';
    const key = m.kind;
    const gR = grp('rotor', key, ex(key));
    const gS = grp('stator', key, ex(key));
    const gC = grp('casing', key, ex(key));
    const sp = m.spool;
    const id = MOD_NAME[m.kind];
    const hotMod = turbine;
    for (const s of m.stages) {
      if (turbine) statorRow(gS, s, key, m.kind === 'hpt' ? mat.tbc : mat.hotBlade, {turbine: true, id: 'ngv'});
      rotorRow(gR, s, key, hotMod ? (m.kind === 'hpt' ? mat.tbc : mat.hotBlade) : mat.blade, sp, {turbine, id, shroud: turbine && m.kind !== 'hpt'});
      if (!turbine) statorRow(gS, s, key, mat.stator, {id: s.i < (m.vsv ?? 0) ? 'vsv' : 'stator'});
    }
    // turbine discs carry cover plates over the blade roots, with the cooling-air holes that feed them
    if (turbine) {
      for (const s of m.stages) {
        const cp = add(gR, mesh(revolve([[s.rh * 0.8, s.zr + s.chord * 0.47], [s.rh * 0.93, s.zr + s.chord * 0.47], [s.rh * 0.93, s.zr + s.chord * 0.44], [s.rh * 0.8, s.zr + s.chord * 0.44]], 128), hotMod ? mat.hotDrum : mat.drum), 'disc', {module: m.kind, stage: s.i + 1});
        spins(cp, sp);
      }
    }
    discs(gR, m, hotMod ? mat.hotDrum : mat.drum, sp, (shaftR[sp] ?? 0.05 * D) * 1.15);
    // the casing over the tips, cone to cone
    const s0 = m.stages[0];
    const s1 = m.stages[m.stages.length - 1];
    casing(gC, turbine ? 'turbine-case' : 'compressor-case', m.z0, m.z1, s0.rt + 0.004 * D, s1.rt + 0.004 * D, 0.012 * D, hotMod ? mat.hotCase : mat.coldCase, {meta: {module: m.kind}});
    // variable stator vanes: a unison ring round the case at each variable row, a lever per vane, an actuator rod
    if (!turbine && m.vsv) {
      for (const s of m.stages.slice(0, m.vsv)) {
        const rr = s.rt + 0.03 * D;
        add(gC, mesh(torusC(rr, 0.004 * D, 6, 96), M.steel).translateZ(s.zs), 'vsv', {stage: s.i + 1});
        const nl = Math.round(s.blades * 1.25);
        const items = [];
        for (let k = 0; k < nl; k++) {
          const a = (k / nl) * TAU + 0.13;
          if (!keep(a)) continue;
          items.push([new V3((rr - 0.012 * D) * Math.cos(a), (rr - 0.012 * D) * Math.sin(a), s.zs), new V3(Math.cos(a), Math.sin(a), 0)]);
        }
        const lev = instances(new THREE.BoxGeometry(0.004 * D, 0.022 * D, 0.012 * D), M.steel, items);
        lev.frustumCulled = false;
        add(gC, lev, 'vsv', {stage: s.i + 1});
      }
      const sa = m.stages[0];
      const sb = m.stages[m.vsv - 1];
      const a0 = 0.6;
      const p0 = new V3((sa.rt + 0.07 * D) * Math.cos(a0), (sa.rt + 0.07 * D) * Math.sin(a0), sa.zs + 0.05 * D);
      const p1 = new V3((sb.rt + 0.07 * D) * Math.cos(a0), (sb.rt + 0.07 * D) * Math.sin(a0), sb.zs - 0.02 * D);
      const act = add(gC, mesh(new THREE.CylinderGeometry(0.012 * D, 0.012 * D, p0.distanceTo(p1), 16), mat.pipe), 'vsv-actuator');
      act.position.copy(p0).lerp(p1, 0.5);
      act.quaternion.setFromUnitVectors(new V3(0, 1, 0), p1.clone().sub(p0).normalize());
    }
  }

  // ------------------------------------------------------------ fan, spinner, booster inlet, bypass (turbofan)
  if (J.fan) {
    const F = J.fan;
    const gR = grp('rotor', 'fan', ex('fan'));
    const fanSpool = hw.gear_ratio ? 'fan' : 'lp';
    if (hw.gear_ratio) J.spools.fan = {rpm: J.spools.lp.rpm / hw.gear_ratio, w: J.spools.lp.w / hw.gear_ratio};
    const comp = hw.fan_material === 'composite';
    const geo = bladeGeometry({
      rh: F.rh * 0.98,
      rt: F.rt * 0.993,
      chordH: F.chord * 0.62,
      chordT: F.chord * (comp ? 1.05 : 1.0),
      stagH: (18 * Math.PI) / 180,
      stagT: (62 * Math.PI) / 180,
      camber: 0.07,
      thick: 0.07,
      sweep: comp ? 0.35 * F.chord : 0.12 * F.chord,
      lean: 0.05 * F.chord,
      nr: Math.max(6, Math.round(12 * DET)),
      nc: Math.max(8, Math.round(14 * DET)),
    });
    geo.translate(0, 0, -F.chord / 2);
    // composite fan blades carry a titanium sheath on the leading edge (u = 0.5 on the loft): metal there, CFRP elsewhere
    let fm = fanMat;
    if (comp) {
      fm = fanMat.clone();
      fm.userData = {...fanMat.userData, blade: true};
      const c = document.createElement('canvas');
      c.width = 256;
      c.height = 4;
      const g2 = c.getContext('2d');
      const grd = g2.createLinearGradient(0, 0, 256, 0);
      for (const [u, col] of [[0, '#000'], [0.435, '#000'], [0.455, '#fff'], [0.545, '#fff'], [0.565, '#000'], [1, '#000']]) grd.addColorStop(u, col);
      g2.fillStyle = grd;
      g2.fillRect(0, 0, 256, 4);
      const metal = new THREE.CanvasTexture(c);
      fm.metalnessMap = metal;
      fm.metalness = 1;
      fm.onBeforeCompile = (sh) => {
        // base colour follows the sheath too: CFRP black blends to titanium grey where the map is white
        sh.fragmentShader = sh.fragmentShader.replace('#include <metalnessmap_fragment>', `#include <metalnessmap_fragment>
          #ifdef USE_METALNESSMAP
            float sheath = texture2D(metalnessMap, vMetalnessMapUv).b;
            diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.62, 0.64, 0.66), sheath);
            metalnessFactor = mix(0.15, 1.0, sheath);
          #endif`);
      };
      fm.customProgramCacheKey = () => 'fan-sheath';
    }
    vibGeo(geo, -F.chord / 2);
    addVib(fm);
    const fan = add(gR, ringOf(geo, fm, F.blades), 'fan');
    blurDisc(gR, F.rh, F.rt * 0.99, -F.chord / 2, 0, F.blades, fanSpool, new THREE.Color(comp ? '#34373b' : '#9aa2ab'), fan, F.chord);
    fan.castShadow = true;
    spins(fan, fanSpool);
    // fan disc with its platforms, and the spinner in front
    const disc = add(gR, mesh(revolve([[F.rh * 0.98, 0.01 * D], [F.rh * 0.98, -F.chord - 0.01 * D], [F.rh * 0.5, -F.chord], [F.rh * 0.5, 0.0], [F.rh * 0.98, 0.01 * D]], 96), mat.disc), 'fan-disc');
    spins(disc, fanSpool);
    const sL = J.zInlet * 0.62;
    const spPts = [];
    for (let i = 0; i <= 24; i++) {
      const u = i / 24;
      spPts.push([F.rh * 0.985 * Math.sin((u * Math.PI) / 2) ** 0.8, sL * (1 - u) + 0.012 * D]);
    }
    spPts.unshift([0, sL + 0.012 * D]);
    // listed tip to root, so the lathe's faces point inward: draw both sides or the spinner looks hollow
    spPts.reverse();
    const spinner = add(gR, mesh(revolve(spPts, 64), mat.spinner), 'spinner');
    spins(spinner, fanSpool);
    boltRing(gR, F.rh * 0.75, 0.012 * D + 0.001, 12, 1, smallBolt, true);
    spins(gR.children[gR.children.length - 1], fanSpool);
    // fan case: a thick containment band over the blades, then the case to the OGVs
    const gC = grp('casing', 'fan', ex('fan'));
    casing(gC, 'fan-case', 0.12 * D, J.ogv.z - J.ogv.chord, R * 1.005, R * 1.005, 0.012 * D, mat.coldCase);
    add(gC, mesh(lc([[R * 1.017, 0.05 * D], [R * 1.07, 0.04 * D], [R * 1.07, -F.chord - 0.01 * D], [R * 1.017, -F.chord - 0.02 * D], [R * 1.017, 0.05 * D]], 128), mat.coldCase), 'fan-case');
    // the abradable honeycomb liner the blade tips run against, set just inside the case wall
    add(gC, mesh(lc([[R * 1.0035, 0.02 * D], [R * 1.0035, -F.chord - 0.005 * D]], 160), mat.abradable), 'abradable');
    // splitter lip, the inner bypass wall (core cowl inside) and the outlet guide vanes across the bypass duct
    const B = J.bypass;
    const core1 = J.combustor.r1 * 1.18;
    const splitPts = [[B.rSplit, J.splitZ], [B.rSplit * 1.02, J.splitZ - 0.04 * D], [B.rSplit * 1.04, J.ogv.z - J.ogv.chord], [core1, J.combustor.z0], [core1, J.combustor.z1], [B.rIn19, B.z1]];
    const inner = splitPts.map(([r, z]) => [r * 0.97 - 0.004 * D, z]).reverse();
    void splitPts;
    void inner;
    const og = {i: 0, zs: J.ogv.z, rh: B.rSplit * 1.03, rt: R * 1.005, chord: J.ogv.chord, blades: Math.round(J.ogv.n / 1.25)};
    statorRow(grp('stator', 'fan', ex('fan')), og, 'ogv', mat.stator, {id: 'ogv'});
    // fan frame struts behind the OGVs (also where the tower shaft runs down)
    const strutGeo = bladeGeometry({rh: B.rSplit * 1.03, rt: R * 1.005, chordH: J.ogv.chord * 1.6, chordT: J.ogv.chord * 1.4, stagH: 0, stagT: 0, camber: 0, thick: 0.16, nr: 2, nc: 8});
    strutGeo.translate(0, 0, J.ogv.z - J.ogv.chord * 1.9);
    add(gC, ringOf(strutGeo, mat.coldCase, 8, Math.PI / 8 - Math.PI / 2, keep), 'fan-frame');
    // booster inlet: the core inlet duct from the splitter to the first booster row
    // geared fan: a star gearbox behind the fan
    if (J.gearbox) {
      const G = J.gearbox;
      const gG = grp('gearbox', 'fan', ex('fan'));
      const zG = G.z - G.len / 2;
      const rRing = G.r * 0.9;
      const tSun = 32;
      const tPl = 17;
      const tRing = 66;
      const pitchR = rRing / (tRing / 2);
      const rs = (tSun / 2) * pitchR;
      const rp = (tPl / 2) * pitchR;
      const w = G.len * 0.55;
      const sun = add(gG, mesh(gearGeo(rs, tSun, w, 0.08), mat.gear), 'fan-gearbox');
      sun.position.z = zG;
      spins(sun, 'lp');
      const ring = add(gG, mesh(revolve([[rRing * 1.02, zG + w / 2], [rRing * 1.12, zG + w / 2], [rRing * 1.12, zG - w / 2], [rRing * 1.02, zG - w / 2], [rRing * 1.02, zG + w / 2]], 96), mat.gear), 'fan-gearbox');
      spins(ring, 'fan');
      for (let k = 0; k < 5; k++) {
        const a = (k / 5) * TAU;
        const pg = new THREE.Group();
        pg.position.set((rs + rp) * Math.cos(a), (rs + rp) * Math.sin(a), zG);
        const pl = add(pg, mesh(gearGeo(rp, tPl, w, 0.1), mat.gear), 'fan-gearbox');
        // in a star gearbox the carrier is fixed: each planet turns on its own pin, opposite the sun
        movers.push((t) => (pl.rotation.z = -J.spools.lp.w * t * (tSun / tPl)));
        gG.add(pg);
      }
      add(gG, mesh(lc([[G.r * 1.05, zG + G.len * 0.6], [G.r * 1.12, zG + G.len * 0.6], [G.r * 1.12, zG - G.len * 0.6], [G.r * 1.05, zG - G.len * 0.6], [G.r * 1.05, zG + G.len * 0.6]], 96), cut(mat.box.clone())), 'fan-gearbox');
    }
  }

  // ------------------------------------------------------------ the compressor face for a turbojet or turboprop:
  // a bullet nose and inlet struts
  if (!J.fan && (fam === 'turbojet' || fam === 'turboprop')) {
    const s0 = J.modules.find((m) => m.kind === 'compressor').stages[0];
    const gC = grp('casing', 'inlet', ex('fan'));
    const zN = J.zInlet * (fam === 'turbojet' ? 0.85 : 0.4);
    const nose = [];
    for (let i = 0; i <= 20; i++) {
      const u = i / 20;
      nose.push([s0.rh * Math.sin((u * Math.PI) / 2) ** 0.7, zN * (1 - u) + 0.02 * D]);
    }
    nose.unshift([0, zN + 0.02 * D]);
    nose.reverse();
    const bullet = add(gC, mesh(revolve(nose, 64), mat.spinner), 'spinner');
    if (fam === 'turbojet') spins(bullet, 'hp');
    casing(gC, 'inlet-case', zN, 0.02 * D, R * 1.06, R * 1.0, 0.014 * D, mat.coldCase);
    const sg = bladeGeometry({rh: s0.rh * 0.9, rt: R * 1.03, chordH: 0.12 * D, chordT: 0.14 * D, stagH: 0, stagT: 0, camber: 0, thick: 0.18, nr: 2, nc: 8});
    sg.translate(0, 0, zN * 0.45);
    add(gC, ringOf(sg, mat.coldCase, fam === 'turbojet' ? 6 : 4, Math.PI / 6, keep), 'inlet-strut');
  }

  // ------------------------------------------------------------ combustor
  if (J.combustor && fam !== 'ramjet') {
    const Cb = J.combustor;
    const g = grp('combustor', 'comb', ex('comb'));
    const gC = grp('casing', 'comb', ex('comb'));
    const L = Cb.z0 - Cb.z1;
    const ri = Cb.r0 + 0.12 * (Cb.r1 - Cb.r0);
    const ro = Cb.r1 - 0.1 * (Cb.r1 - Cb.r0);
    // the liner: an annulus with a domed front, tapering into the turbine nozzle at the back
    const hptIn = J.stations.find((s) => s.id === 'hpt-in');
    const out = [[ri + 0.25 * (ro - ri), Cb.z0], [ro, Cb.z0 - 0.15 * L], [ro, Cb.z0 - 0.6 * L], [hptIn.rt, Cb.z1]];
    const inn = [[hptIn.rh, Cb.z1], [ri, Cb.z0 - 0.6 * L], [ri, Cb.z0 - 0.15 * L], [ri + 0.25 * (ro - ri), Cb.z0]];
    add(g, mesh(lc([...out, ...inn], 96), mat.combLiner), 'combustor');
    // dilution-hole rows: dark rings punched in the liner
    for (const u of [0.35, 0.55]) for (const r of [ro, ri]) add(g, mesh(torusC(r, 0.006 * D, 6, 96), mat.liner).translateZ(Cb.z0 - u * L), 'combustor');
    // the flame: the gas inside the liner, glowing at the turbine-inlet temperature
    // primary zone near stoichiometric (taken 450 K over the exit, capped at 2300 K), then dilution air brings the
    // gas down to the turbine-inlet temperature the solver gives
    const Tpk = Math.min(2300, Cb.T + 450);
    const Tc = (u) => (u < 0.3 ? Cb.Tin + (Tpk - Cb.Tin) * Math.sin((u / 0.3) * (Math.PI / 2)) : Tpk - (Tpk - Cb.T) * Math.min(1, (u - 0.3) / 0.45));
    const Vc = J.at((Cb.z0 + Cb.z1) / 2).V * 0.5;
    const fm = flameMat(Tc, Cb.z0, Cb.z1, Vc, 0.9);
    const fl = [[ri + 0.3 * (ro - ri), Cb.z0 - 0.08 * L], [ro * 0.985, Cb.z0 - 0.2 * L], [ro * 0.97, Cb.z0 - 0.62 * L], [hptIn.rt * 0.98, Cb.z1 + 0.02 * L], [hptIn.rh * 1.02, Cb.z1 + 0.02 * L], [ri * 1.015, Cb.z0 - 0.62 * L], [ri * 1.015, Cb.z0 - 0.2 * L], [ri + 0.3 * (ro - ri), Cb.z0 - 0.08 * L]];
    addFlame(g, lc(fl, 128), fm);
    // fuel nozzles through the outer case into the dome, and two igniters
    const caseR = ro + 0.12 * (Cb.r1 - Cb.r0) + 0.02 * D;
    casing(gC, 'combustor-case', Cb.z0 + 0.03 * D, Cb.z1 - 0.01 * D, caseR, caseR * 0.97, 0.012 * D, mat.hotCase);
    const nz = Cb.nozzles;
    const stem = new THREE.CylinderGeometry(0.01 * D, 0.01 * D, caseR - (ri + ro) / 2 + 0.05 * D, 10).translate(0, (caseR + (ri + ro) / 2) / 2 + 0.02 * D, 0);
    const head = new THREE.CylinderGeometry(0.022 * D, 0.016 * D, 0.03 * D, 14).rotateX(Math.PI / 2).translate(0, (ri + ro) / 2, 0);
    const swirl = new THREE.TorusGeometry(0.03 * D, 0.006 * D, 6, 16).translate(0, (ri + ro) / 2, -0.012 * D);
    for (const [geo, m] of [[stem, mat.pipe], [head, M.steel], [swirl, M.steel]]) {
      const ng = geo.clone().translate(0, 0, Cb.z0 + 0.01 * D);
      add(g, ringOf(ng, m, nz, 0, keep), 'fuel-nozzle');
    }
    const igGeo = new THREE.CylinderGeometry(0.012 * D, 0.012 * D, caseR - ro + 0.06 * D, 10).translate(0, (caseR + ro) / 2 + 0.03 * D, 0).translate(0, 0, Cb.z0 - 0.2 * L);
    const ig = add(g, ringOf(igGeo, M.ceramic, 2, Math.PI * 0.85, keep), 'igniter');
    void ig;
    // fuel manifold round the case, a pigtail to each nozzle
    const gD = grp('dress', 'comb', ex('comb'));
    const mR = caseR + 0.06 * D;
    add(gD, mesh(torusC(mR, 0.009 * D, 8, 160).translate(0, 0, Cb.z0 + 0.035 * D), mat.pipe), 'fuel-manifold');
    add(gD, mesh(torusC(mR + 0.02 * D, 0.007 * D, 8, 160).translate(0, 0, Cb.z0 + 0.02 * D), mat.braid), 'fuel-manifold');
    const pig = [];
    for (let k = 0; k < nz; k++) {
      const a = (k / nz) * TAU;
      if (!keep(a)) continue;
      const p0 = new V3(mR * Math.cos(a), mR * Math.sin(a), Cb.z0 + 0.035 * D);
      const p1 = new V3((caseR + 0.035 * D) * Math.cos(a + 0.05), (caseR + 0.035 * D) * Math.sin(a + 0.05), Cb.z0 + 0.012 * D);
      const p2 = new V3((caseR + 0.012 * D) * Math.cos(a), (caseR + 0.012 * D) * Math.sin(a), Cb.z0 + 0.01 * D);
      pig.push(tube([p0, p1, p2], 0.004 * D, false, 8));
    }
    const pm = new THREE.Mesh(mergeGeos(pig), mat.pipe);
    add(gD, pm, 'fuel-manifold');
  }

  // ------------------------------------------------------------ shafts and bearings
  if (J.modules.length) {
    const g = grp('shaft', 'shafts');
    const zF = J.fan ? -0.02 * D : J.modules[0].z0 + 0.02 * D;
    const lastLP = J.modules.filter((m) => m.spool === 'lp' || m.spool === 'pt').pop();
    const lastHP = J.modules.filter((m) => m.spool === 'hp').pop();
    const firstHP = J.modules.find((m) => m.spool === 'hp');
    const shaftSeg = (r, z0, z1, name, id) => {
      const s = add(g, mesh(new THREE.CylinderGeometry(r, r, z0 - z1, 32).rotateX(Math.PI / 2).translate(0, 0, (z0 + z1) / 2), mat.shaft), id);
      spins(s, name);
      return s;
    };
    if (lastLP) shaftSeg(shaftR.lp, J.prop ? J.rgb.z1 : zF, lastLP.z1 - 0.03 * D, lastLP.spool, lastLP.spool === 'pt' ? 'pt-shaft' : 'lp-shaft');
    const ipm = J.modules.filter((m) => m.spool === 'ip');
    if (ipm.length) shaftSeg(shaftR.ip, ipm[0].z0, ipm[ipm.length - 1].z1, 'ip', 'ip-shaft');
    if (firstHP) shaftSeg(shaftR.hp, firstHP.z0, lastHP.z1, 'hp', 'hp-shaft');
    // bearings: an outer race, a cage of balls, at the front and back of each spool
    const bearing = (r, z, name) => {
      const bg = new THREE.Group();
      bg.position.z = z;
      add(bg, mesh(new THREE.TorusGeometry(r * 1.55, r * 0.14, 8, 40), M.steel), 'bearing');
      add(bg, mesh(new THREE.TorusGeometry(r * 1.12, r * 0.1, 8, 40), M.steel), 'bearing');
      const balls = [];
      const nb = 14;
      for (let k = 0; k < nb; k++) {
        const a = (k / nb) * TAU;
        balls.push([new V3(r * 1.33 * Math.cos(a), r * 1.33 * Math.sin(a), 0), new V3(0, 1, 0)]);
      }
      const bm = instances(new THREE.SphereGeometry(r * 0.17, 10, 8), mat.bearing, balls);
      bm.frustumCulled = false;
      const cage = new THREE.Group();
      cage.add(bm);
      bg.add(cage);
      // the ball set turns at roughly half the shaft speed
      spins(cage, name, 0.45);
      g.add(bg);
    };
    if (firstHP) {
      bearing(shaftR.hp, firstHP.z0 - 0.02 * D, 'hp');
      bearing(shaftR.hp, lastHP.z1 + 0.02 * D, 'hp');
    }
    if (lastLP) {
      bearing(shaftR.lp * 1.4, zF - 0.06 * D, lastLP.spool);
      bearing(shaftR.lp * 1.4, lastLP.z1 - 0.01 * D, lastLP.spool);
    }
  }

  // ------------------------------------------------------------ the turboprop's impeller, propeller and gearbox
  if (J.impeller) {
    const I = J.impeller;
    const gR = grp('rotor', 'impeller', ex('hpc'));
    // the hub sweeps from axial to radial; blades stand on it, back-swept at the rim
    const hubPts = [];
    for (let i = 0; i <= 16; i++) {
      const u = i / 16;
      hubPts.push([I.rIn + (I.rOut - I.rIn) * Math.sin((u * Math.PI) / 2) ** 2, I.z - u * I.len]);
    }
    hubPts.push([I.rOut, I.z - I.len - 0.02 * D], [0.05 * D, I.z - I.len - 0.04 * D], [0.05 * D, I.z]);
    const hubM = add(gR, mesh(revolve(hubPts, 96), mat.drum), 'impeller');
    spins(hubM, 'hp');
    const bl = [];
    const nb = I.blades;
    const bpos = [];
    const bidx = [];
    const NS = 14;
    for (let i = 0; i <= NS; i++) {
      const u = i / NS;
      const rh = I.rIn + (I.rOut - I.rIn) * Math.sin((u * Math.PI) / 2) ** 2;
      const rs = I.rEye + (I.rOut - I.rEye) * Math.sin((u * Math.PI) / 2) ** 1.6;
      const zh = I.z - u * I.len;
      const zs = I.z - u * I.len * 0.82;
      const th = -0.6 * u * u;
      bpos.push(rh * Math.sin(th), rh * Math.cos(th), zh, rs * Math.sin(th), rs * Math.cos(th), zs);
      if (i) {
        const a = (i - 1) * 2;
        bidx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3);
      }
    }
    const bgeo = new THREE.BufferGeometry();
    bgeo.setAttribute('position', new THREE.Float32BufferAttribute(bpos, 3));
    bgeo.setIndex(bidx);
    bgeo.computeVertexNormals();
    const bmat = mat.blade.clone();
    bmat.side = THREE.DoubleSide;
    const blades = add(gR, ringOf(bgeo, bmat, nb), 'impeller');
    spins(blades, 'hp');
    void bl;
    // the shroud and diffuser case over it
    const gC = grp('casing', 'impeller', ex('hpc'));
    const sh = [];
    for (let i = 0; i <= 12; i++) {
      const u = i / 12;
      sh.push([I.rEye * 1.02 + (I.rOut * 1.02 - I.rEye * 1.02) * Math.sin((u * Math.PI) / 2) ** 1.6, I.z - u * I.len * 0.82]);
    }
    sh.push([I.rOut * 1.25, I.z - I.len * 0.85], [I.rOut * 1.25, I.z - I.len - 0.06 * D]);
    const shIn = sh.map(([r, z]) => [r + 0.012 * D, z + 0.004 * D]).reverse();
    add(gC, mesh(lc([...sh, ...shIn, sh[0]], 96), mat.coldCase), 'impeller-case');
  }
  if (J.prop) {
    const P = J.prop;
    const gP = grp('rotor', 'prop', new V3(0, 0, 0.9 * D));
    const rH = 0.16 * D;
    const geo = bladeGeometry({rh: rH * 0.9, rt: P.D / 2, chordH: 0.24 * D, chordT: 0.12 * D, stagH: (30 * Math.PI) / 180, stagT: (72 * Math.PI) / 180, camber: 0.05, thick: 0.1, sweep: -0.06 * P.D, lean: 0.08 * P.D, nr: 14, nc: 12});
    geo.translate(0, 0, P.z);
    add(gP, ringOf(geo, mat.composite, P.blades), 'propeller');
    const sp = [];
    for (let i = 0; i <= 20; i++) {
      const u = i / 20;
      sp.push([rH * Math.sin((u * Math.PI) / 2) ** 0.75, P.z + 0.45 * D * (1 - u)]);
    }
    sp.unshift([0, P.z + 0.45 * D]);
    sp.push([rH, P.z - 0.18 * D], [0.04 * D, P.z - 0.2 * D]);
    add(gP, mesh(revolve(sp, 64), mat.spinner), 'spinner');
    for (const c of gP.children) spins(c, 'prop');
    // reduction gearbox: two epicyclic stages from power-turbine speed down to the propeller
    const G = J.rgb;
    const gG = grp('gearbox', 'rgb', new V3(0, 0, 0.55 * D));
    const zg = (G.z0 + G.z1) / 2;
    add(gG, mesh(lc([[0.05 * D, G.z0], [G.r * 0.78, G.z0 - 0.05 * D], [G.r, zg + 0.1 * D], [G.r, zg - 0.15 * D], [R * 1.08, G.z1], [R * 0.6, G.z1], [0.05 * D, G.z0 - 0.02 * D]], 96), cut(mat.box.clone())), 'rgb');
    const stageR = Math.sqrt(P.ratio);
    for (const [k, zz] of [[0, zg + 0.06 * D], [1, zg - 0.1 * D]]) {
      const ringR = G.r * 0.62;
      const tS = 22;
      const tP = Math.round((tS * (stageR - 2)) / 2) || 11;
      const tR = tS + 2 * tP;
      const pr = ringR / (tR / 2);
      const rs = (tS / 2) * pr;
      const rp = (tP / 2) * pr;
      const sun = add(gG, mesh(gearGeo(rs, tS, 0.07 * D, 0.1), mat.gear), 'rgb');
      sun.position.z = zz;
      // first stage sun on the power turbine shaft, second on the first stage's carrier
      const wS = k === 0 ? J.spools.pt.w : J.spools.pt.w / stageR;
      movers.push((t) => (sun.rotation.z = wS * t));
      const carrier = new THREE.Group();
      carrier.position.z = zz;
      for (let j = 0; j < 4; j++) {
        const a = (j / 4) * TAU;
        const pl = mesh(gearGeo(rp, tP, 0.07 * D, 0.1), mat.gear);
        pl.position.set((rs + rp) * Math.cos(a), (rs + rp) * Math.sin(a), 0);
        part(pl, 'rgb');
        carrier.add(pl);
        movers.push((t) => (pl.rotation.z = -wS * t * (tS / tP)));
      }
      gG.add(carrier);
      // with the ring fixed, the carrier turns at sun speed over (1 + ring/sun)
      movers.push((t) => (carrier.rotation.z = (wS * t) / (1 + tR / tS)));
      add(gG, mesh(revolve([[ringR * 1.02, zz + 0.04 * D], [ringR * 1.1, zz + 0.04 * D], [ringR * 1.1, zz - 0.04 * D], [ringR * 1.02, zz - 0.04 * D], [ringR * 1.02, zz + 0.04 * D]], 96), mat.gear), 'rgb');
    }
    // the annular intake screen between gearbox and compressor
    const s0 = J.modules[0].stages[0];
    const scr = lc([[R * 1.08, G.z1], [s0.rt * 1.02, 0.03 * D]], 96);
    const sm = cut(new THREE.MeshStandardMaterial({color: '#6d737a', metalness: 0.8, roughness: 0.5, wireframe: true}));
    add(grp('casing', 'inlet', ex('fan')), mesh(scr, sm), 'intake-screen');
  }

  // ------------------------------------------------------------ nozzles
  if (J.nozzle && fam !== 'ramjet' && fam !== 'scramjet') {
    const N = J.nozzle;
    const g = grp('casing', 'nozzle', ex('nozzle'));
    if (N.plug) {
      // turbine rear frame struts, the core nozzle sleeve and the centre plug
      const lt = J.stations.find((s) => s.id === 'lpt-exit');
      const fg = bladeGeometry({rh: lt.rh * 0.98, rt: lt.rt * 1.02, chordH: 0.08 * D, chordT: 0.08 * D, stagH: 0.1, stagT: 0.12, camber: 0, thick: 0.14, nr: 2, nc: 8});
      fg.translate(0, 0, N.z0 - 0.05 * D);
      add(g, ringOf(fg, mat.inconel, 12, 0, keep), 'trf');
      // the nozzle sleeve sits inside the core cowl's trailing edge, so the two never share a surface
      casing(g, 'core-nozzle', N.z0, N.z1 + 0.01 * D, lt.rt + 0.006 * D, N.rOut - 0.004 * D, 0.004 * D, mat.inconel, {flanges: false});
      const pl = [[lt.rh * 0.99, N.z0 + 0.02 * D]];
      for (let i = 1; i <= 16; i++) {
        const u = i / 16;
        pl.push([lt.rh * (1 - u ** 1.6) * 0.99, N.z0 - u * (N.z0 - N.z1 + 0.35 * D)]);
      }
      pl.push([0, N.z1 - 0.35 * D]);
      add(g, mesh(lc(pl, 96), mat.inconel), 'plug');
    } else {
      const lt = J.stations.find((s) => s.id === 'lpt-exit');
      if (N.reheat) {
        // jet pipe with spray rings and V-gutter flame holders, the reheat flame, then the variable nozzle's petals
        const A = J.afterburner;
        const gA = grp('combustor', 'ab', ex('ab'));
        casing(g, 'afterburner', A.z0 + 0.1 * D, A.z1, lt.rt * 1.02, A.r, 0.012 * D, mat.hotCase, {seg: 12});
        add(g, mesh(lc([[lt.rh, A.z0 + 0.1 * D], [0.02 * D, A.z0 - 0.25 * D]], 48), mat.hotCase), 'tail-cone');
        for (const [rr, zz] of [[A.r * 0.45, A.z0 - 0.3 * D], [A.r * 0.75, A.z0 - 0.35 * D]]) {
          add(gA, mesh(lc([[rr - 0.025 * D, zz - 0.04 * D], [rr, zz], [rr + 0.025 * D, zz - 0.04 * D]], 96), mat.hotCase), 'flameholder');
          add(gA, mesh(torusC(rr, 0.005 * D, 6, 96).translate(0, 0, zz + 0.08 * D), mat.pipe), 'spray-ring');
        }
        // reheat: flame sheets grow from each gutter and fill the pipe toward the nozzle
        const T5 = J.stations.find((x) => x.id === 'lpt-exit').Tt;
        const za = A.z0 - 0.35 * D;
        const Ta = (u) => T5 + (A.T - T5) * Math.min(1, u / 0.45) ** 0.7;
        const fa = flameMat(Ta, za, A.z1, J.at(za).V, 0.75);
        const sheets = [];
        for (let i = 0; i <= 24; i++) {
          const u = i / 24;
          sheets.push([A.r * (0.3 + 0.62 * Math.sqrt(u)), za - u * (za - A.z1)]);
        }
        const back = sheets.map(([r, z]) => [r * 0.35 * (1 - (za - z) / (za - A.z1)) + 0.01 * D, z]).reverse();
        addFlame(gA, lc([...sheets, ...back, sheets[0]], 128), fa);
      } else {
        casing(g, 'tailpipe', N.z0, N.z1, lt.rt * 1.02, N.rOut, 0.01 * D, mat.hotCase);
        add(g, mesh(lc([[lt.rh, N.z0], [0.02 * D, N.z0 - 0.3 * D]], 48), mat.hotCase), 'tail-cone');
      }
      // convergent nozzle petals, set to the exit area the solver needs
      const zP = N.reheat ? J.afterburner.z1 : N.z1 + 0.1 * D;
      const rP0 = N.reheat ? J.afterburner.r : N.rIn;
      const np = 18;
      const len = 0.28 * D;
      const ang = Math.atan2(rP0 - N.rOut, len);
      const petal = new THREE.BoxGeometry(((TAU * (rP0 + N.rOut)) / 2 / np) * 1.08, 0.006 * D, len).translate(0, 0, -len / 2);
      const items = [];
      const grpP = new THREE.Group();
      for (let k = 0; k < np; k++) {
        const a = (k / np) * TAU;
        if (!keep(a)) continue;
        const pm = mesh(petal, mat.hotCase);
        pm.position.set(rP0 * Math.cos(a), rP0 * Math.sin(a), zP);
        pm.rotation.set(0, 0, a - Math.PI / 2);
        pm.rotateX(-ang);
        part(pm, 'nozzle-petals');
        grpP.add(pm);
      }
      g.add(grpP);
      void items;
      // the exhaust plume with its shock cells, behind the nozzle exit
      const s9 = J.stations.find((x) => x.id === 'nozzle');
      const P = plumeOf(s9.Pt, 2 * N.rOut);
      J.plume = P;
      plume(grp('flow', 'plume'), N.z1 - 0.02 * D, N.rOut, N.reheat ? J.afterburner.T * 0.92 : s9.Tt, s9.V, P, N.reheat ? 0.9 : 0.35);
    }
    // the turboprop's cowling: from behind the spinner, over the gearbox and the engine, tapering to the exhaust
    if (J.prop) {
      const gN = grp('nacelle', 'nacelle', new V3(0, 0.9 * D, 0));
      const zs0 = J.prop.z - 0.16 * D;
      const zg = (J.rgb.z0 + J.rgb.z1) / 2;
      const rS = 0.17 * D;
      const rM = Math.max(J.rgb.r * 1.18, (J.impeller?.rOut ?? 0) * 1.25 + 0.04 * D);
      const zE = N.z1 + 0.02 * D;
      const rE = N.rOut + 0.04 * D;
      const ctrl = [new V3(rS, zs0, 0), new V3(rM * 0.92, zg + 0.08 * D, 0), new V3(rM, zg - 0.15 * D, 0), new V3(rM * 0.98, J.combustor.z0, 0), new V3(rM * 0.9, J.combustor.z1 - 0.1 * D, 0), new V3(rE, zE, 0)];
      const out = new THREE.CatmullRomCurve3(ctrl, false, 'centripetal').getPoints(90).map((v) => [v.x, v.y]);
      const inn = out.map(([r, z]) => [r - 0.012 * D, z]).reverse();
      add(gN, mesh(lc([...out, ...inn, out[0]], 160), mat.nacelle), 'nacelle');
    }
    // the bypass nozzle: the core cowl and the fan nozzle's trailing edge (turbofan)
    if (J.bypass) {
      const B = J.bypass;
      const gN = grp('nacelle', 'nacelle', new V3(0, 0.9 * D, 0));
      // Nacelle: an elliptical lip round the highlight, the crest at a third of its length, then a boat-tail to a
      // thin trailing edge at the fan nozzle exit. Inside: the lip to the throat, a diffuser to the fan case, and the
      // bypass duct's outer wall converging to the exit area the solver needs.
      const zh = J.zInlet * 0.92;
      const zTE = B.z1;
      const rh = R * 1.085;
      const rmax = R * 1.2;
      const zm = zh - 0.32 * (zh - zTE);
      const rte = B.rOut19 + 0.008 * D;
      const zth = zh - 0.06 * D;
      const rth = R * 1.035;
      const zf0 = 0.12 * D;
      const zf1 = J.ogv.z - J.ogv.chord;
      const ell = (e) => Math.sqrt(Math.max(0, 1 - (1 - e) * (1 - e)));
      const sm = (u) => u * u * (3 - 2 * u);
      const outer = [];
      for (let i = 0; i <= 28; i++) {
        const e = i / 28;
        outer.push([rh + (rmax - rh) * ell(e), zh - e * (zh - zm)]);
      }
      for (let i = 1; i <= 40; i++) {
        const u = i / 40;
        outer.push([rmax - (rmax - rte) * u ** 1.9, zm - u * (zm - zTE)]);
      }
      const inner = [];
      for (let i = 0; i <= 40; i++) {
        const u = i / 40;
        inner.push([R * 1.006 + (B.rOut19 - R * 1.006) * sm(u), zf1 - u * (zf1 - zTE)]);
      }
      inner.reverse();
      inner.push([R * 1.006, zf1], [R * 1.075, zf1], [R * 1.075, zf0], [R * 1.006, zf0]);
      for (let i = 1; i <= 16; i++) {
        const u = i / 16;
        inner.push([R * 1.006 + (rth - R * 1.006) * sm(u), zf0 + u * (zth - zf0)]);
      }
      for (let i = 1; i <= 20; i++) {
        const e = 1 - i / 20;
        inner.push([rh - (rh - rth) * ell(e), zh - e * (zh - zth)]);
      }
      add(gN, mesh(lc([...inner, ...outer, inner[0]], 160), mat.nacelle), 'nacelle');
      // acoustic liner: perforated skin over honeycomb, lining the inlet from the throat to the fan case
      const al = [];
      for (let i = 0; i <= 16; i++) {
        const u = i / 16;
        al.push([R * 1.006 + (rth - R * 1.006) * sm(u) - 0.0015 * D, zf0 + u * (zth - zf0)]);
      }
      add(gN, mesh(lc(al, 160), mat.acoustic), 'acoustic-liner');
      // the thrust reverser's cascade vanes, between the nacelle's skins (seen in the cut)
      // each row sits halfway between the skins at its station, and fills a third of the gap
      const zc0 = zf1 - 0.04 * D;
      const zc1 = zc0 - 0.2 * D;
      const skinAt = (pts, z) => {
        for (let i = 1; i < pts.length; i++) {
          const [ra, za] = pts[i - 1];
          const [rb, zb] = pts[i];
          if ((z - za) * (z - zb) <= 0 && za !== zb) return ra + ((rb - ra) * (z - za)) / (zb - za);
        }
        return null;
      };
      const bypassWall = inner.slice(0, 41);
      for (let k = 0; k < 6; k++) {
        const zz = zc0 - ((k + 0.5) / 6) * (zc0 - zc1);
        const ro = skinAt(outer, zz);
        const ri = skinAt(bypassWall, zz);
        if (ro == null || ri == null || ro - ri < 0.02 * D) continue;
        const h = 0.35 * (ro - ri);
        const vg = new THREE.BoxGeometry(0.004 * D, h, 0.025 * D).rotateX(0.6).translate(0, (ro + ri) / 2, zz);
        void vg;
      }
      // core cowl: one smooth surface from the splitter lip over the core, out of the bypass nozzle, tapering to
      // the core nozzle's exit
      const N = J.nozzle;
      const ctrl = [new V3(B.rSplit, J.splitZ, 0), new V3(B.rSplit * 1.04, zf1, 0), new V3(Math.max(J.combustor.r1 * 1.2, B.rIn19 * 1.06), (J.combustor.z0 + J.combustor.z1) / 2, 0), new V3(B.rIn19, B.z1, 0), new V3((B.rIn19 + N.rOut) / 2 * 1.04, (B.z1 + N.z1) / 2, 0), new V3(N.rOut + 0.012 * D, N.z1 + 0.005 * D, 0)];
      const cv = new THREE.CatmullRomCurve3(ctrl, false, 'centripetal').getPoints(90).map((v) => [v.x, v.y]);
      const cin = cv.map(([r, z], i) => [r - Math.max(0.008 * D, 0.03 * r) * Math.min(1, i / 4), z]).reverse();
      add(grp('casing', 'fan', ex('fan')), mesh(lc([...cv, ...cin, cv[0]], 128), mat.nacelle), 'core-cowl');
    }
  }

  // ------------------------------------------------------------ ramjet
  if (fam === 'ramjet') {
    const S = J.spike;
    const N = J.nozzle;
    const Cb = J.combustor;
    const g = grp('casing', 'ram', new V3());
    const gB = grp('casing', 'ramBody', new V3(0, 0, 0.35 * D));
    const gF = grp('combustor', 'comb', new V3(0, 0, -0.3 * D));
    const gN = grp('casing', 'ramNozzle', new V3(0, 0, -0.55 * D));
    const gX = grp('dress', 'ramAcc', new V3(0, 0.25 * D, 0));
    const rHub = S.rMax;
    const rL = Cb.r1;
    const tw = 0.012 * D;
    const rCase = R * 1.04;

    // ---- the centre body: double-cone spike, cylinder through the burner, tail cone as the nozzle plug. It is whole
    // (not cut), like the centre body of a museum cutaway, so the cones read in full inside the opened duct.
    {
      const sp = [[0, S.zTip + 0.004 * D], [0.004 * D, S.zTip]];
      for (let i = 1; i <= 24; i++) {
        const z = S.zTip - (i / 24) * (S.zTip - S.zKnee);
        sp.push([J.spikeR(z), z]);
      }
      for (let i = 1; i <= 12; i++) {
        const z = S.zKnee - (i / 12) * (S.zKnee - S.zShoulder);
        sp.push([J.spikeR(z), z]);
      }
      const cbz0 = S.zShoulder - 0.1 * D;
      sp.push([rHub, cbz0], [0, cbz0]);
      add(gB, mesh(revolve(sp, segs(128)), mat.titanium), 'spike');
      // the centre body proper, with panel joints, through the diffuser and burner
      add(gB, mesh(revolve([[0, cbz0], [rHub, cbz0], [rHub, N.zPlug0], [0, N.zPlug0]], segs(96)), mat.hotDrum), 'centre-body');
      for (const z of [cbz0, -0.66 * D, N.zPlug0 + 0.02 * D]) add(gB, mesh(new THREE.TorusGeometry(rHub * 1.004, 0.004 * D, 8, segs(96)).translate(0, 0, z), mat.pipe), 'centre-body');
      // boundary-layer bleed: a band of slots on the second cone, just ahead of the shoulder
      const zs = (S.zKnee + S.zShoulder) / 2 - 0.02 * D;
      const slot = roundedBox(0.012 * D, 0.004 * D, 0.05 * D, 0.002 * D).translate(0, J.spikeR(zs) + 0.0005 * D, zs);
      add(gB, ringOf(slot, mat.plastic, 36, 0, null), 'spike');
      // a pitot-static boom on the nose
      add(gB, mesh(new THREE.CylinderGeometry(0.004 * D, 0.006 * D, 0.22 * D, 16).rotateX(Math.PI / 2).translate(0, 0, S.zTip + 0.11 * D), mat.pipe), 'pitot');
      add(gB, mesh(new THREE.CylinderGeometry(0.0015 * D, 0.004 * D, 0.03 * D, 12).rotateX(Math.PI / 2).translate(0, 0, S.zTip + 0.235 * D), mat.pipe), 'pitot');
      // the tail cone: the nozzle's plug, in a heat-resisting alloy
      const pl = [[0, N.zPlug0]];
      for (let i = 0; i <= 30; i++) {
        const z = N.zPlug0 - (i / 30) * (N.zPlug0 - N.z1);
        pl.push([Math.max(0.006 * D, J.plugR(z)), z]);
      }
      pl.push([0, N.z1 - 0.004 * D]);
      add(gN, mesh(revolve(pl, segs(128)), mat.hotDrum), 'plug');
      add(gN, mesh(new THREE.TorusGeometry(rHub * 1.006, 0.006 * D, 8, segs(96)).translate(0, 0, N.zPlug0), mat.pipe), 'plug');
    }

    // ---- struts: four airfoil struts hold the centre body in the diffuser
    {
      const zS = -0.32 * D;
      const strut = bladeGeometry({rh: rHub * 0.98, rt: J.at(zS).rt + tw, chordH: 0.26 * D, chordT: 0.22 * D, stagH: 0, stagT: 0, camber: 0, thick: 0.09, nr: 3, nc: 10});
      strut.translate(0, 0, zS);
      add(gB, ringOf(strut, mat.titanium, 4, Math.PI / 4, keep), 'spike-strut');
    }

    // ---- the cowl: inlet ring with a sharp lip, a bulged burner casing with stiffening ribs, and the nozzle shroud
    // closing onto the plug. Each section is built over the kept arc so the cut shows its wall.
    const zDif = -0.62 * D;
    const zBur1 = Cb.z1 - 0.02 * D;
    const bulgeR = (u) => rCase + 0.065 * D * Math.sin(u * Math.PI) ** 0.6;
    {
      const inner = [];
      const outer = [];
      for (let i = 0; i <= 24; i++) {
        const u = i / 24;
        const z = S.zCowl + (zDif - S.zCowl) * u;
        inner.push([S.rLip + (rL + 0.02 * D - S.rLip) * (u * u * (3 - 2 * u)), z]);
        // the outer line leaves the lip at a shallow external angle and blends into a constant diameter
        outer.push([S.rLip + 0.004 * D + (rCase - S.rLip - 0.004 * D) * Math.sin((Math.min(1, u * 2.2) * Math.PI) / 2), z]);
      }
      add(g, mesh(lc([...inner, ...outer.reverse(), inner[0]], 128), mat.inlet), 'cowl');
    }
    {
      // burner casing: inner wall clear of the liner (the cooling-air gap), outer wall bulged over the burner
      const inner = [];
      const outer = [];
      for (let i = 0; i <= 24; i++) {
        const u = i / 24;
        const z = zDif + (zBur1 - zDif) * u;
        inner.push([rL + 0.02 * D + 0.03 * D * Math.sin(u * Math.PI) ** 0.6, z]);
        outer.push([bulgeR(u), z]);
      }
      add(g, mesh(lc([...inner, ...outer.reverse(), inner[0]], 128), mat.hotCase), 'burner-case');
      for (let i = 1; i <= 5; i++) {
        const u = i / 6;
        add(g, mesh(torusC(bulgeR(u) + 0.004 * D, 0.007 * D, 8, segs(128)).translate(0, 0, zDif + (zBur1 - zDif) * u), mat.hotCase), 'burner-case');
      }
      for (const [z, dir] of [[zDif, 1], [zBur1, -1]]) {
        add(g, mesh(lc([[rCase - 0.005 * D, z - 0.012 * D], [rCase + 0.04 * D, z - 0.012 * D], [rCase + 0.04 * D, z + 0.012 * D], [rCase - 0.005 * D, z + 0.012 * D], [rCase - 0.005 * D, z - 0.012 * D]], 128), mat.hotCase), 'burner-case');
        boltRing(g, rCase + 0.026 * D, z + dir * 0.012 * D, 40, dir, smallBolt);
      }
    }
    {
      // the nozzle shroud: from the burner flange the wall converges onto the plug; its sharp exit lip is the throat
      const inner = [];
      const outer = [];
      for (let i = 0; i <= 20; i++) {
        const u = i / 20;
        const z = zBur1 + (N.zt - zBur1) * u;
        inner.push([rL + 0.02 * D + (N.rT - rL - 0.02 * D) * (u * u * (3 - 2 * u)), z]);
        outer.push([rCase + (N.rT + 0.01 * D - rCase) * Math.pow(u, 1.6), z]);
      }
      add(gN, mesh(lc([...inner, ...outer.reverse(), inner[0]], 128), mat.inconel), 'nozzle-shroud');
    }

    // ---- the burner: a perforated liner, a heat shield on the centre body, the fuel spray ring with its injectors,
    // two V-gutter rings tied by radial gutters, and an igniter through the casing
    {
      add(gF, mesh(lc([[rL, Cb.z0 + 0.02 * D], [rL, Cb.z1], [rL + tw * 0.6, Cb.z1], [rL + tw * 0.6, Cb.z0 + 0.02 * D], [rL, Cb.z0 + 0.02 * D]], 128), mat.inconel), 'liner');
      add(gF, mesh(revolve([[rHub * 1.006, Cb.z0], [rHub * 1.006, Cb.z1], [rHub * 1.014, Cb.z1], [rHub * 1.014, Cb.z0], [rHub * 1.006, Cb.z0]], segs(96)), mat.liner), 'liner');
      const rS = (rHub + rL) / 2;
      const zSp = Cb.z0 + 0.1 * D;
      add(gF, mesh(torusC(rS, 0.01 * D, 8, segs(128)).translate(0, 0, zSp), mat.pipe), 'spray-ring');
      const peg = new THREE.CylinderGeometry(0.004 * D, 0.006 * D, 0.03 * D, 8).rotateX(Math.PI / 2).translate(0, rS, zSp - 0.018 * D);
      add(gF, ringOf(peg, M.steel, Cb.nozzles, 0, keep), 'spray-ring');
      const zg = Cb.z0 - 0.08 * D;
      const vg = (rr, zz, w) => lc([[rr - w, zz - 0.05 * D], [rr, zz], [rr + w, zz - 0.05 * D], [rr + w * 0.82, zz - 0.05 * D], [rr, zz - 0.012 * D], [rr - w * 0.82, zz - 0.05 * D], [rr - w, zz - 0.05 * D]], 128);
      const rG = [rHub + (rL - rHub) * 0.3, rHub + (rL - rHub) * 0.72];
      rG.forEach((rr, k) => add(gF, mesh(vg(rr, zg - 0.03 * D * k, 0.028 * D), mat.inconel), 'flameholder'));
      const spoke = new THREE.BoxGeometry(0.026 * D, rG[1] - rG[0], 0.012 * D).translate(0, (rG[0] + rG[1]) / 2, zg - 0.03 * D);
      add(gF, ringOf(spoke, mat.inconel, 8, Math.PI / 8, keep), 'flameholder');
      // the igniter: a boss on the casing, the plug through it, and its lead
      const aI = 0.82 * Math.PI;
      const cI = new V3(Math.cos(aI), Math.sin(aI), 0);
      const zI = zg - 0.12 * D;
      const rI = rCase + 0.05 * D;
      const boss = add(gX, mesh(new THREE.CylinderGeometry(0.03 * D, 0.034 * D, 0.04 * D, 20), mat.hotCase), 'igniter');
      boss.position.copy(cI).multiplyScalar(rI).setZ(zI);
      boss.quaternion.setFromUnitVectors(new V3(0, 1, 0), cI);
      const plug = add(gX, mesh(new THREE.CylinderGeometry(0.014 * D, 0.014 * D, 0.09 * D, 6), M.steel), 'igniter');
      plug.position.copy(cI).multiplyScalar(rI + 0.05 * D).setZ(zI);
      plug.quaternion.copy(boss.quaternion);
      const lead = [cI.clone().multiplyScalar(rI + 0.095 * D).setZ(zI), cI.clone().multiplyScalar(rI + 0.13 * D).setZ(zI + 0.06 * D), new V3(-0.12 * D, R * 1.25, zI + 0.3 * D)];
      add(gX, mesh(tube(lead, 0.008 * D, false, 32), mat.braid), 'igniter');
    }

    // ---- outside: the fuel manifold round the burner with a feed to each injector, the mounting pylon on top,
    // thermocouple and pressure bosses
    {
      const zM = Cb.z0 + 0.1 * D;
      const rM = rCase + 0.07 * D;
      add(gX, mesh(torusC(rM, 0.014 * D, 10, segs(128)).translate(0, 0, zM), mat.pipe), 'fuel-manifold');
      const feed = new THREE.CylinderGeometry(0.005 * D, 0.005 * D, rM - rCase + 0.01 * D, 8).translate(0, (rM + rCase) / 2, zM);
      add(gX, ringOf(feed, mat.pipe, 8, 0, keep), 'fuel-manifold');
      const nut = new THREE.CylinderGeometry(0.01 * D, 0.01 * D, 0.012 * D, 6).translate(0, rCase + 0.006 * D, zM);
      add(gX, ringOf(nut, M.steel, 8, 0, keep), 'fuel-manifold');
      const aF = 0.62 * Math.PI;
      const cF = new V3(Math.cos(aF), Math.sin(aF), 0);
      add(gX, mesh(tube([cF.clone().multiplyScalar(rM).setZ(zM), cF.clone().multiplyScalar(rM + 0.06 * D).setZ(zM + 0.04 * D), new V3(-0.03 * D, R * 1.3, zM + 0.2 * D), new V3(0, R * 1.36, zM + 0.35 * D)], 0.012 * D, false, 48), mat.pipe), 'fuel-manifold');
      // the pylon: a faired beam on top with two hanger lugs
      const pz0 = 0.05 * D;
      const pz1 = Cb.z0 - 0.75 * D;
      const py = rCase + 0.1 * D;
      const beam = add(gX, mesh(roundedBox(0.08 * D, 0.12 * D, pz0 - pz1, 0.03 * D), mat.stand), 'mount');
      beam.position.set(0, py + 0.03 * D, (pz0 + pz1) / 2);
      for (const z of [pz0 - 0.12 * D, pz1 + 0.12 * D]) {
        const lug = add(gX, mesh(new THREE.TorusGeometry(0.03 * D, 0.012 * D, 10, 24), M.steel), 'mount');
        lug.position.set(0, py + 0.12 * D, z);
        lug.rotation.y = Math.PI / 2;
        const foot = add(gX, mesh(roundedBox(0.1 * D, 0.03 * D, 0.1 * D, 0.01 * D), mat.stand), 'mount');
        foot.position.set(0, py - 0.045 * D, z);
      }
      // thermocouple and static-pressure bosses along the visible side
      for (const [a, z, id] of [[1.05 * Math.PI, Cb.z0 - 0.35 * D, 'thermocouple'], [1.05 * Math.PI, Cb.z0 - 0.75 * D, 'thermocouple'], [1.2 * Math.PI, zDif + 0.25 * D, 'pressure-tap']]) {
        const c = new V3(Math.cos(a), Math.sin(a), 0);
        const u = (zDif - z) / (zDif - zBur1);
        const r = (u > 0 && u < 1 ? bulgeR(u) : rCase) + 0.012 * D;
        const b = add(gX, mesh(new THREE.CylinderGeometry(0.012 * D, 0.016 * D, 0.03 * D, 12), M.steel), id);
        b.position.copy(c).multiplyScalar(r).setZ(z);
        b.quaternion.setFromUnitVectors(new V3(0, 1, 0), c);
        add(gX, mesh(tube([b.position.clone().addScaledVector(c, 0.015 * D), b.position.clone().addScaledVector(c, 0.06 * D).setZ(z + 0.05 * D), new V3(c.x * R * 0.4, R * 1.3, z + 0.12 * D)], 0.004 * D, false, 24), mat.harness), id);
      }
    }

    // ---- the flame: sheets spread from each gutter's wake until they fill the annulus, neck through the throat and
    // hug the plug as the jet expands round it
    {
      const zg = Cb.z0 - 0.12 * D;
      const Tr = (u) => Cb.Tin + (Cb.T - Cb.Tin) * Math.min(1, u / 0.45) ** 0.6;
      const fm = flameMat(Tr, zg, N.z1, J.at(Cb.z1).V, 1.1);
      const outer = [];
      const inner = [];
      for (let i = 0; i <= 40; i++) {
        const u = i / 40;
        const z = zg - u * (zg - N.z1);
        const a = J.at(z);
        const grow = Math.min(1, Math.sqrt(Math.max(0, (zg - z) / (zg - Cb.z1 * 0.85))));
        const mid = (a.rh + a.rt) / 2;
        const half = (a.rt - a.rh) / 2;
        const pr = J.plugR(z);
        outer.push([Math.max(pr + 0.01 * D, mid + half * (0.35 + 0.6 * grow)), z]);
        inner.push([Math.max(0.004 * D, pr * 1.01, mid - half * (0.35 + 0.6 * grow)), z]);
      }
      addFlame(gF, lc([...outer, ...inner.reverse(), outer[0]], 128), fm);
    }
    const s9 = J.stations.find((x) => x.id === 'nozzle');
    J.plume = plumeOf(s9.Pt, 2 * N.rOut);
    plume(grp('flow', 'plume'), N.z1 - 0.01 * D, N.rOut, s9.Tt * 0.9, s9.V, J.plume, 0.55);

    // ---- shocks: the tip shock and the knee shock both land on the cowl lip (the design point), then the terminal
    // normal shock just inside the lip turns the flow subsonic
    {
      const M0 = J.mach;
      add(grp('shock', 'shock'), mesh(revolve([[0.001, S.zTip], [S.rLip, S.zCowl]], 96), schlieren(rhoJump(M0 * Math.sin(J.shock.beta)))), 'shock');
      add(grp('shock', 'shock'), mesh(revolve([[S.r1, S.zKnee], [S.rLip, S.zCowl]], 96), schlieren(rhoJump(Math.max(1.02, J.shock.M1 * Math.sin(J.shock.beta2 + S.half - S.half1))))), 'shock');
      // the knee shock turns the air a little more and slows it again; the terminal shock stands in what is left
      const M2 = Math.max(1.05, J.shock.M1 * 0.85);
      J.normalShock = {M: M2, jump: rhoJump(M2)};
      const zN = S.zCowl - 0.08 * D;
      add(grp('shock', 'shock'), mesh(revolve([[J.spikeR(zN) * 1.01, zN], [J.at(zN).rt * 0.995, zN - 0.015 * D]], 96), schlieren(rhoJump(M2))), 'normal-shock');
    }
  }

  // ------------------------------------------------------------ scramjet (two-dimensional)
  // A lifting body in the X-43 family: a flat-topped, chined airframe whose whole underside is the engine. The forebody
  // ramps compress the air, the cowl (its front a hinged door) captures it, struts inject hydrogen in the combustor, and
  // the aft underside is the nozzle's expansion ramp. The cut shows the bays inside: nose ballast, avionics, the
  // hydrogen and silane bottles and the fuel feed to the struts, the tail actuators.
  if (fam === 'scramjet') {
    const S = J.scram;
    const W = S.W;
    const g = grp('casing', 'scram');
    const gB = grp('casing', 'scramBody', new V3(0, 0.45, 0));
    const gC = grp('casing', 'scramCowl', new V3(0, -0.4, 0));
    const gT = grp('casing', 'scramTail', new V3(0, 0.75, -0.25));
    const gI = grp('dress', 'scramInt', new V3(0, 0.12, 0));
    const skin = cut(alloy('paintWhite', {repeat: [10, 30]}));
    const carbon = cut(alloy('cfrp', {repeat: [4, 12]}));
    Object.assign(carbon, {clearcoat: 0.25, roughness: 0.58, envMapIntensity: 0.55});
    // the inside of the skin is primed dark, so the cut reads as a wall with an inside rather than a shell seen through
    const primer = cut(phys({color: '#3c433f', metalness: 0.15, roughness: 0.75}));
    const cutFace = phys({color: '#b4b8bc', metalness: 0.1, roughness: 0.85, side: THREE.DoubleSide});
    const zN = J.zInlet;
    const zE = S.zN1;
    const Ltot = zN - zE;
    const lin = (a, b, n) => Array.from({length: n + 1}, (_, i) => a + ((b - a) * i) / n);
    // sampled finer near the nose, where the planform and the top change fastest
    const zs = [...lin(zN, zN - 0.6, 30), ...lin(zN - 0.6, zE, 160).slice(1)];
    const sides = KEEP ? [1] : [1, -1];

    // planform: a sharp nose widening to the full span by 42% of the length; side profile: a top rising from the nose
    // and easing down over the last quarter to a blunt base
    const Wb = W * 2.2;
    const uOf = (z) => (zN - z) / Ltot;
    const halfW = (z) => (Wb / 2) * (0.05 + 0.95 * Math.min(1, uOf(z) / 0.42) ** 0.8);
    const yTop = (z) => {
      const u = uOf(z);
      const aft = u > 0.72 ? 1 - 0.28 * ((u - 0.72) / 0.28) ** 1.4 : 1;
      return S.yU(zN) + 0.012 + 0.38 * Math.min(1, u / 0.45) ** 0.65 * aft;
    };
    S.halfW = halfW;
    // the half section from the chine round to the top centreline: x in half-widths, y in heights above the underside
    const SEC = [[-1, 0], [-0.98, 0.08], [-0.93, 0.26], [-0.85, 0.5], [-0.74, 0.72], [-0.6, 0.87], [-0.4, 0.96], [-0.2, 0.995], [0, 1]];
    const CH = 3; // the first points are the dark chine band
    const secAt = (z, pts, inset = 0) => {
      const w = halfW(z) - inset;
      const y0 = S.yU(z) + inset;
      const h = yTop(z) - S.yU(z) - 2 * inset;
      return pts.map(([sx, sy]) => [sx * w, y0 + sy * h]);
    };
    const full = (pts) => (KEEP ? pts : [...pts, ...pts.slice(0, -1).reverse().map(([x, y]) => [-x, y])]);
    const yAt = (x, z) => {
      const s = -Math.min(1, Math.abs(x) / halfW(z));
      for (let i = 1; i < SEC.length; i++) {
        if (s <= SEC[i][0] + 1e-9) {
          const [x0, y0] = SEC[i - 1];
          const [x1, y1] = SEC[i];
          return S.yU(z) + (y0 + ((y1 - y0) * (s - x0)) / (x1 - x0)) * (yTop(z) - S.yU(z));
        }
      }
      return yTop(z);
    };
    // a surface lofted through sections between z0 and z1 (z0 > z1)
    const loft = (z0, z1, sectionOf) => {
      const zz = zs.filter((z) => z < z0 - 1e-6 && z > z1 + 1e-6);
      zz.unshift(z0);
      zz.push(z1);
      const pos = [];
      const uv = [];
      const idx = [];
      zz.forEach((z, j) => {
        const ring = sectionOf(z);
        const n = ring.length;
        ring.forEach(([x, y], i) => {
          pos.push(x, y, z);
          uv.push(i / (n - 1), uOf(z));
        });
        if (j) {
          const a = (j - 1) * n;
          const b = j * n;
          for (let i = 0; i < n - 1; i++) idx.push(a + i, b + i, b + i + 1, a + i, b + i + 1, a + i + 1);
        }
      });
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
      geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
      geo.setIndex(idx);
      geo.computeVertexNormals();
      return geo;
    };
    const mirror = (sd) => (pts) => pts.map(([x, y]) => [sd * x, y]);
    const polyShape = (pts) => {
      const sh = new THREE.Shape();
      sh.moveTo(...pts[0]);
      for (const p of pts.slice(1)) sh.lineTo(...p);
      sh.closePath();
      return sh;
    };

    // ---- the airframe: carbon-carbon nose cap and chine bands, a painted upper skin, the underside panels
    const zNose = zN - 0.45;
    for (const sd of sides) {
      const mr = mirror(sd);
      add(gB, mesh(loft(zN, zE, (z) => mr(secAt(z, SEC.slice(0, CH + 1)))), carbon), 'airframe');
      add(gB, mesh(loft(zN, zNose, (z) => mr(secAt(z, SEC.slice(CH)))), carbon), 'nose-tip');
      add(gB, mesh(loft(zNose, zE, (z) => mr(secAt(z, SEC.slice(CH)))), skin), 'airframe');
      const bottom = (z) => mr(secAt(z, [[-1, 0], [0, 0]]));
      add(gB, mesh(loft(zN, zNose, bottom), carbon), 'nose-tip');
      add(gB, mesh(loft(zNose, 0, bottom), mat.tps), 'forebody');
      add(gB, mesh(loft(0, S.zC1, bottom), mat.hotCase), 'isolator');
      add(gB, mesh(loft(S.zC1, zE, bottom), mat.inconel), 'nozzle-ramp');
    }
    // panel seams round the section, and across the underside at the ramp corner and the ends of the flow path
    {
      const seamM = mat.plastic;
      for (const z of [zNose, zN - 1.8, S.zC0 + 0.45, zE + 0.9]) {
        const pts = full(secAt(z, SEC)).map(([x, y]) => new V3(x * 1.002, y + 0.0015, z));
        add(gB, mesh(tube(pts, 0.0035, false, 96), seamM), 'airframe');
      }
      const wd = KEEP ? halfW(0) : 2 * halfW(0);
      for (const z of [zN / 2, 0, S.zC1]) {
        const s = add(gB, mesh(new THREE.BoxGeometry(wd, 0.004, 0.008), seamM), z === S.zC1 ? 'nozzle-ramp' : 'forebody');
        s.position.set(KEEP ? -wd / 2 : 0, S.yU(z) - 0.001, z);
      }
    }
    // the blunt base, and the nose tip closed
    for (const [z, id] of [[zE, 'base'], [zN, 'nose-tip']]) {
      const pts = full(secAt(z, SEC));
      if (KEEP) pts.push([0, S.yU(z)]);
      add(gB, mesh(new THREE.ShapeGeometry(polyShape(pts)).translate(0, 0, z), carbon), id);
    }
    // boundary-layer trips: a row of small wedges across the forebody that make its boundary layer turbulent, so it
    // stays attached through the inlet's compression
    {
      const zt = zN - 0.6;
      const items = [];
      for (let k = 0; k < 16; k++) {
        const x = -W / 2 + ((k + 0.5) * W) / 16;
        if (KEEP && x > 0) continue;
        items.push([new V3(x, S.yU(zt) - 0.006, zt), new V3(0, -1, 0)]);
      }
      const tr = instances(new THREE.ConeGeometry(0.012, 0.014, 4).rotateY(Math.PI / 4), carbon, items);
      tr.frustumCulled = false;
      add(gB, tr, 'bl-trip');
    }

    // ---- the section face, hollow between the bulkheads
    const tW = 0.05;
    const BH = [zN - 0.5, zN - 1.0, zN - 1.8, S.zC0 + 0.45, S.zC1 + 0.1, zE + 0.9, zE + 0.06];
    if (KEEP) {
      const prof = new THREE.Shape();
      prof.moveTo(zs[0], S.yU(zs[0]));
      for (const z of zs) prof.lineTo(z, S.yU(z));
      for (const z of zs.slice().reverse()) prof.lineTo(z, yTop(z));
      for (let i = 0; i + 1 < BH.length; i++) {
        const za = BH[i] - (i ? 0.012 : 0);
        const zb = BH[i + 1] + (i + 2 < BH.length ? 0.012 : 0);
        const zz = [za, ...zs.filter((z) => z < za && z > zb), zb];
        const hole = new THREE.Path();
        hole.moveTo(za, S.yU(za) + tW);
        for (const z of zz.slice(1)) hole.lineTo(z, S.yU(z) + tW);
        for (const z of zz.slice().reverse()) hole.lineTo(z, yTop(z) - tW);
        prof.holes.push(hole);
      }
      add(gB, mesh(new THREE.ShapeGeometry(prof, 2).rotateY(-Math.PI / 2), cutFace), 'airframe');
      // the skin's inner face, a wall thickness in from the outside, over the hollow bays
      const inner = (z) => [[0, S.yU(z) + tW], ...secAt(z, SEC, tW)];
      add(gB, mesh(loft(BH[0], BH[BH.length - 1], inner), primer), 'airframe');
    }

    // ---- the cowl: a sharp lip, a wall thickening behind it, a cavity flameholder in its inner face, a tapered end.
    // The first 0.35 m is a door hinged at its rear, as on the X-43A: closed for the boost, opened to start the engine.
    const zEnd = S.zCowlEnd;
    const th = (z) => 0.008 + (Math.min(0.13, 0.008 + -z * 0.32) - 0.008) * Math.max(0, Math.min(1, (z - zEnd) / 0.35));
    const yO = (z) => S.yL(z) - th(z);
    const zc0 = S.zC0 - 0.12;
    const dep = 0.045;
    const zc1 = zc0 - 5 * dep;
    const cowlShape = (z0, z1) => {
      const zz = [z0, ...zs.filter((z) => z < z0 - 1e-4 && z > z1 + 1e-4), z1];
      const inner = [];
      for (const z of zz) {
        if (z < zc0 && z > zc1) continue;
        if (z <= zc1 && inner.length && inner[inner.length - 1][0] >= zc0) {
          inner.push([zc0, S.yL(zc0)], [zc0, S.yL(zc0) - dep], [zc1 + dep / Math.tan((22.5 * Math.PI) / 180), S.yL(zc1) - dep], [zc1, S.yL(zc1)]);
        }
        inner.push([z, S.yL(z)]);
      }
      return polyShape([...inner, ...zz.slice().reverse().map((z) => [z, yO(z)])]);
    };
    const wd = KEEP ? W / 2 + 0.02 : W + 0.04;
    const xR = KEEP ? 0 : W / 2 + 0.02;
    const span = (sh) => new THREE.ExtrudeGeometry(sh, {depth: wd, bevelEnabled: false}).rotateY(-Math.PI / 2).translate(xR, 0, 0);
    const zDoor = -0.35;
    add(gC, mesh(span(cowlShape(0, zDoor)), mat.hotCase), 'cowl-door');
    add(gC, mesh(span(cowlShape(zDoor - 0.005, zEnd)), mat.hotCase), 'cowl');
    {
      const xc = xR - wd / 2;
      const hinge = add(gC, mesh(new THREE.CylinderGeometry(0.011, 0.011, wd, 16).rotateZ(Math.PI / 2), M.steel), 'cowl-door');
      hinge.position.set(xc, yO(zDoor) - 0.006, zDoor - 0.002);
      for (const f of [0.15, 0.5, 0.85]) {
        const k = add(gC, mesh(new THREE.CylinderGeometry(0.019, 0.019, 0.05, 20).rotateZ(Math.PI / 2), mat.hotCase), 'cowl-door');
        k.position.set(xR - wd * f, yO(zDoor) - 0.008, zDoor - 0.002);
      }
      // the door's actuator, in a fairing under the cowl
      const act = add(gC, mesh(roundedBox(0.07, 0.045, 0.42, 0.018), mat.hotCase), 'cowl-door');
      act.position.set(-W / 4, yO(-0.62) - 0.02, -0.62);
      // panel seams across the cowl's underside
      for (const z of [-1.05, -1.65]) {
        const s = add(gC, mesh(new THREE.BoxGeometry(wd, 0.004, 0.008), mat.plastic), 'cowl');
        s.position.set(xc, yO(z) - 0.001, z);
      }
      // the cavity's floor, sooted by the flame it holds
      const fl = add(gC, mesh(new THREE.BoxGeometry(wd - 0.004, 0.003, zc0 - zc1 - dep / Math.tan((22.5 * Math.PI) / 180)), carbon), 'cavity');
      fl.position.set(xc, S.yL(zc0) - dep + 0.0016, (zc0 + zc1 + dep / Math.tan((22.5 * Math.PI) / 180)) / 2);
    }
    // sidewalls: from the body down to the cowl, their leading edges swept back from the body to the cowl lip so air
    // the inlet cannot swallow spills sideways (the near one is cut away in the cutaway view)
    for (const sd of sides) {
      const zSW = 0.75;
      const pts = [];
      for (const z of [zSW, ...zs.filter((z) => z < zSW && z > zEnd), zEnd]) pts.push([z, S.yU(z) + 0.01]);
      for (const z of [zEnd, ...zs.filter((z) => z < 0 && z > zEnd)].reverse()) pts.push([z, yO(z) - 0.004]);
      pts.push([0, yO(0) - 0.004]);
      const geo = new THREE.ExtrudeGeometry(polyShape(pts), {depth: 0.024, bevelEnabled: true, bevelThickness: 0.006, bevelSize: 0.006, bevelSegments: 2});
      geo.rotateY(-Math.PI / 2).translate(sd > 0 ? -W / 2 - 0.009 : W / 2 + 0.033, 0, 0);
      add(gC, mesh(geo, mat.hotCase), 'sidewall');
    }

    // nozzle fences: short walls either side of the expansion ramp, from the cowl's end to the base, framing the exit
    for (const sd of sides) {
      const pts = [];
      for (const z of [zEnd, ...zs.filter((z) => z < zEnd && z > zE), zE]) pts.push([z, S.yU(z) + 0.01]);
      pts.push([zE, S.yU(zE) - 0.07], [zEnd, yO(zEnd) - 0.004]);
      const geo = new THREE.ExtrudeGeometry(polyShape(pts), {depth: 0.024, bevelEnabled: true, bevelThickness: 0.006, bevelSize: 0.006, bevelSegments: 2});
      geo.rotateY(-Math.PI / 2).translate(sd > 0 ? -W / 2 - 0.009 : W / 2 + 0.033, 0, 0);
      add(gB, mesh(geo, mat.inconel), 'nozzle-fence');
    }
    // the exhaust: still supersonic as it leaves the cowl, expanding against the ramp above and the outside air below,
    // then spreading as a plume past the base
    {
      const zx0 = zEnd + 0.05;
      const zx1 = zE - 1.1;
      const Tx = (J.stations.find((x) => x.id === 'comb-exit')?.Tt ?? S.T) * 0.8;
      const fm = flameMat((u) => Tx * (1 - 0.5 * u), zx0, zx1, J.at(S.zN1).V, 0.3);
      const t10 = Math.tan((10 * Math.PI) / 180);
      const t6 = Math.tan((6 * Math.PI) / 180);
      const pos = [];
      const idx = [];
      const zz = lin(zx0, zx1, 70);
      for (const z of zz) {
        const yt = z >= zE ? S.yU(z) - 0.012 : S.yU(zE) - 0.012 + (zE - z) * t10 * 0.3;
        const yb = S.yL(zEnd) + 0.01 - (zEnd - z) * t6;
        const hw = W / 2 - 0.02 + Math.max(0, zE - z) * 0.08;
        pos.push(-hw, yb, z, hw, yb, z, -hw, yt, z, hw, yt, z);
      }
      for (let i = 1; i < zz.length; i++) {
        const a = (i - 1) * 4;
        const b = i * 4;
        idx.push(a, b, b + 1, a, b + 1, a + 1, a + 2, b + 3, b + 2, a + 2, a + 3, b + 3, a, a + 2, b + 2, a, b + 2, b, a + 1, b + 1, b + 3, a + 1, b + 3, a + 3);
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
      geo.setIndex(idx);
      geo.computeVertexNormals();
      addFlame(grp('flow', 'exhaust'), geo, fm, 'exhaust');
    }

    // regeneratively cooled panels on the combustor walls: fuel runs through channels in the wall before it is burned,
    // fed and collected by a manifold across the width at each end; seen here on the cut face
    {
      const za = S.zC0 + 0.25;
      const zb = S.zC1 - 0.35;
      for (const [yOf, sgn, z0, gg] of [[S.yU, 1, za, gB], [S.yL, -1, zc1 - 0.01, gC]]) {
        const zz = zs.filter((z) => z <= z0 && z >= zb);
        const sh = new THREE.Shape();
        sh.moveTo(zz[0], yOf(zz[0]));
        for (const z of zz) sh.lineTo(z, yOf(z));
        for (const z of zz.slice().reverse()) sh.lineTo(z, yOf(z) + sgn * 0.03);
        const cap = new THREE.ShapeGeometry(sh, 2).rotateY(-Math.PI / 2).translate(KEEP ? 0.002 : W / 2 + 0.002, 0, 0);
        add(gg, mesh(cap, mat.coolPanel), 'cooled-panel');
        for (const z of [z0, zb]) {
          const man = add(gg, mesh(new THREE.CylinderGeometry(0.022, 0.022, (KEEP ? W / 2 : W) + 0.006, 20).rotateZ(Math.PI / 2), mat.coolPanel), 'cooled-panel');
          man.position.set(KEEP ? -W / 4 + 0.003 : 0, yOf(z) + sgn * 0.045, z);
        }
      }
    }
    // fuel-injecting struts across the combustor entry
    const yC = (S.yU(S.zC0) + S.yL(S.zC0)) / 2;
    const hC = S.yU(S.zC0) - S.yL(S.zC0);
    const strutX = [];
    for (let k = 0; k < S.struts; k++) {
      const x = -W / 2 + ((k + 1) * W) / (S.struts + 1);
      strutX.push(x);
      const sh = polyShape([[0.18, 0], [0, 0.025], [-0.08, 0.025], [-0.08, -0.025], [0, -0.025]]);
      const geo = new THREE.ExtrudeGeometry(sh, {depth: hC, bevelEnabled: false});
      geo.rotateX(-Math.PI / 2);
      geo.rotateY(-Math.PI / 2);
      const m = add(g, mesh(geo, mat.titanium), 'strut');
      m.position.set(x, yC - hC / 2, S.zC0 + 0.05);
      m.rotation.set(0, Math.PI / 2, 0);
    }

    // ---- the tail: twin canted fins with rudders, all-moving wings at the chines
    const plate = (pts, d = 0.024) =>
      new THREE.ExtrudeGeometry(polyShape(pts), {depth: d, bevelEnabled: true, bevelThickness: 0.006, bevelSize: 0.005, bevelSegments: 2}).translate(0, 0, -d / 2).rotateY(-Math.PI / 2);
    {
      const cr = 0.95;
      const sp = 0.55;
      const zLE = zE + 0.97;
      for (const sd of KEEP ? [1] : [1, -1]) {
        const x = -sd * 0.55 * halfW(zE + 0.5);
        const fg = new THREE.Group();
        fg.position.set(x, yAt(x, zLE) - 0.012, zLE);
        fg.rotation.x = -Math.atan((yAt(x, zLE) - yAt(x, zLE - cr)) / cr);
        const tilt = new THREE.Group();
        tilt.rotation.z = sd * 0.2;
        tilt.add(part(mesh(plate([[0, 0], [-0.66, 0], [-0.766, sp], [-0.5, sp]]), carbon), 'fin'));
        tilt.add(part(mesh(plate([[-0.672, 0], [-cr, 0], [-0.88, sp], [-0.776, sp]]), skin), 'rudder'));
        const hingeR = mesh(new THREE.CylinderGeometry(0.008, 0.008, sp, 10), M.steel);
        hingeR.position.set(0, sp / 2, -0.7225);
        hingeR.rotation.x = -Math.atan2(0.107, sp);
        tilt.add(part(hingeR, 'rudder'));
        fg.add(tilt);
        gT.add(fg);
      }
      const wc = 0.75;
      const zW = zE + 0.95;
      for (const sd of sides) {
        const wg = new THREE.Group();
        wg.position.set(-sd * (halfW(zW) - 0.01), S.yU(zW - wc / 2) + 0.025, zW);
        wg.rotation.x = Math.atan((S.yU(zW - wc) - S.yU(zW)) / wc) * 0.8;
        const wm = part(mesh(plate([[0, 0], [-wc, 0], [-0.75, 0.5], [-0.45, 0.5]], 0.03), skin), 'wing');
        wm.rotation.z = sd * Math.PI / 2;
        wg.add(wm);
        const piv = part(mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.1, 20).rotateZ(Math.PI / 2), carbon), 'wing');
        piv.position.set(-sd * 0.02, 0, -wc * 0.45);
        wg.add(piv);
        gT.add(wg);
      }
    }

    // ---- inside, seen through the cut
    if (KEEP) {
      // frames: rings following the skin, open in the middle (the hydrogen bottle passes through them), and stringers
      // running along the skin between them
      const xT = -0.34;
      const rT = 0.13;
      const yT = 0.0;
      const fd = 0.06;
      for (const z of BH.slice(0, -1)) {
        const out = [[0, S.yU(z) + tW], ...secAt(z, SEC, tW)];
        const inn = [[0, S.yU(z) + tW + fd], ...secAt(z, SEC, tW + fd)];
        add(gI, mesh(new THREE.ExtrudeGeometry(polyShape([...out, ...inn.reverse()]), {depth: 0.022, bevelEnabled: false}).translate(0, 0, z - 0.011), mat.aluminium), 'bulkhead');
      }
      for (const p of [[-0.5, 0], SEC[2], SEC[4], SEC[6], [0, 1]]) {
        const pts = [];
        for (let z = BH[0] - 0.02; z > BH[BH.length - 1]; z -= 0.15) {
          const [x, y] = secAt(z, [p], tW + 0.012)[0];
          pts.push(new V3(Math.min(x, -0.012), y, z));
        }
        add(gI, mesh(tube(pts, 0.011, false, 96), mat.aluminium), 'bulkhead');
      }
      // nose ballast: dense metal that puts the centre of mass far enough forward for stability
      const zb = (BH[0] + BH[1]) / 2;
      const slope = (z) => (S.yU(z + 0.01) - S.yU(z - 0.01)) / 0.02;
      const bal = add(gI, mesh(roundedBox(0.17, 0.09, 0.36, 0.012), M.steel), 'ballast');
      bal.position.set(-0.1, S.yU(zb) + tW + 0.045, zb);
      bal.rotation.x = -Math.atan(slope(zb));
      // avionics: flight computer, battery and inertial unit on a level shelf across the bay (the floor slopes with the
      // ramp), with their harness running aft
      const zs0 = BH[1] - 0.03;
      const zs1 = BH[2] + 0.03;
      const yS = S.yU(zs0) + tW + 0.03;
      {
        const sh = polyShape([[0, zs0], [-(halfW(zs0) - tW - 0.05), zs0], [-(halfW(zs1) - tW - 0.05), zs1], [0, zs1]]);
        add(gI, mesh(new THREE.ExtrudeGeometry(sh, {depth: 0.012, bevelEnabled: false}).rotateX(Math.PI / 2).translate(0, yS, 0), mat.aluminium), 'avionics');
      }
      for (const [w, h, d, x, z] of [[0.18, 0.11, 0.2, -0.12, BH[1] - 0.17], [0.26, 0.12, 0.3, -0.19, BH[1] - 0.52], [0.15, 0.1, 0.15, -0.12, BH[2] + 0.12]]) {
        const b = add(gI, mesh(roundedBox(w, h, d, 0.01), mat.box), 'avionics');
        b.position.set(x, yS + h / 2, z);
        for (let j = 0; j < 4; j++) {
          const fin = mesh(new THREE.BoxGeometry(w * 0.9, 0.008, 0.003), mat.box);
          fin.position.set(0, h / 2 + 0.004, -d * 0.35 + (j * d * 0.7) / 3);
          b.add(fin);
        }
      }
      const harness = [];
      for (let z = BH[1] - 0.2; z > zE + 0.3; z -= 0.25) harness.push(new V3(-0.1, yAt(-0.1, z) - tW - 0.03, z));
      add(gI, mesh(tube(harness, 0.009, false, 96), mat.harness), 'avionics');
      // the hydrogen bottle: a composite-overwrapped vessel through the middle bay, on two straps
      const zf = BH[2] - 0.17;
      const za = BH[4] + 0.2;
      const cap = [];
      for (let i = 0; i <= 10; i++) cap.push([Math.max(0.001, rT * Math.sin((i / 10) * (Math.PI / 2))), zf + rT * Math.cos((i / 10) * (Math.PI / 2))]);
      for (let i = 0; i <= 10; i++) cap.push([Math.max(0.001, rT * Math.cos((i / 10) * (Math.PI / 2))), za - rT * Math.sin((i / 10) * (Math.PI / 2))]);
      const tank = add(gI, mesh(revolve(cap, 48), mat.composite), 'h2-tank');
      tank.position.set(xT, yT, 0);
      // two straps, each on a cradle down to the floor
      for (const z of [zf - 0.25, za + 0.25]) {
        const s = add(gI, mesh(new THREE.TorusGeometry(rT + 0.006, 0.009, 8, 48), mat.aluminium), 'h2-tank');
        s.position.set(xT, yT, z);
        const yF = S.yU(z) + tW;
        const h = yT - rT - yF + 0.02;
        const c = add(gI, mesh(roundedBox(0.2, h, 0.05, 0.01), mat.aluminium), 'h2-tank');
        c.position.set(xT, yF + h / 2, z);
      }
      const boss = add(gI, mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.06, 16).rotateX(Math.PI / 2), M.steel), 'h2-tank');
      boss.position.set(xT, yT, za - rT - 0.02);
      // the silane bottle: silane lights on contact with air, so a little of it mixed into the hydrogen at start-up
      // ignites the engine
      const zs2 = (BH[4] + BH[5]) / 2;
      const sil = add(gI, mesh(new THREE.SphereGeometry(0.1, 32, 20), mat.composite), 'silane');
      sil.position.set(-0.32, S.yU(zs2) + tW + 0.13, zs2);
      {
        const h = 0.13 - 0.07;
        const c = add(gI, mesh(new THREE.CylinderGeometry(0.06, 0.08, h, 24), mat.aluminium), 'silane');
        c.position.set(-0.32, S.yU(zs2) + tW + h / 2, zs2);
      }
      // the fuel feed: bottle to a valve and regulator, down to a manifold above the combustor roof that feeds each strut
      const yM = S.yU(S.zC0) + 0.06;
      const zM = S.zC0 + 0.02;
      const feed = [new V3(xT, yT, za - rT - 0.05), new V3(xT, yT - 0.05, za - rT - 0.25), new V3(xT + 0.02, yM + 0.12, zM - 0.25), new V3(-0.22, yM, zM)];
      add(gI, mesh(tube(feed, 0.014, false, 48), mat.pipe), 'h2-line');
      const sline = [new V3(-0.32, sil.position.y - 0.08, zs2 + 0.06), new V3(-0.3, yM + 0.03, zs2 + 0.5), new V3(-0.27, yM, zM - 0.35), new V3(-0.24, yM, zM - 0.02)];
      add(gI, mesh(tube(sline, 0.008, false, 48), mat.pipe), 'h2-line');
      const valve = add(gI, mesh(roundedBox(0.07, 0.07, 0.09, 0.012), mat.box), 'h2-line');
      valve.position.copy(feed[1]).lerp(feed[2], 0.45);
      const reg = add(gI, mesh(new THREE.CylinderGeometry(0.032, 0.032, 0.07, 20), mat.aluminium), 'h2-line');
      reg.position.copy(valve.position).add(new V3(0, 0.07, 0));
      const man = add(gI, mesh(new THREE.CylinderGeometry(0.018, 0.018, W / 2 + 0.04, 16).rotateZ(Math.PI / 2), mat.pipe), 'h2-manifold');
      man.position.set(-W / 4 + 0.02, yM, zM);
      for (const x of strutX) {
        if (x > 1e-6) continue;
        const stub = add(gI, mesh(new THREE.CylinderGeometry(0.01, 0.01, yM - S.yU(S.zC0) + 0.01, 10), mat.pipe), 'h2-manifold');
        stub.position.set(x, (yM + S.yU(S.zC0)) / 2, zM);
      }
      // tail actuators: one turning each wing's torque shaft, one each fin's rudder
      const zA = (BH[5] + BH[6]) / 2;
      for (const [x, y, len, pitch] of [[-0.48, S.yU(zA) + tW + 0.06, 0.42, -Math.atan(slope(zA))], [-0.3, yAt(-0.3, zA) - tW - 0.07, 0.36, 0]]) {
        const ag = new THREE.Group();
        ag.position.set(x, y, zA);
        ag.rotation.x = pitch;
        ag.add(part(mesh(new THREE.CylinderGeometry(0.035, 0.035, len, 20).rotateX(Math.PI / 2), mat.aluminium), 'actuator'));
        const rod = part(mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.18, 12).rotateX(Math.PI / 2), M.steel), 'actuator');
        rod.position.z = -len / 2 - 0.08;
        ag.add(rod);
        // a clevis bracket to the structure at the front end
        const br = part(mesh(roundedBox(0.06, 0.05, 0.04, 0.008), mat.aluminium), 'actuator');
        br.position.set(0, y > 0.1 ? 0.04 : -0.04, len / 2 + 0.02);
        ag.add(br);
        gI.add(ag);
      }
      const zW = zE + 0.95 - 0.75 * 0.45;
      const ts = add(gI, mesh(new THREE.CylinderGeometry(0.018, 0.018, halfW(zW) - 0.4, 12).rotateZ(Math.PI / 2), M.steel), 'actuator');
      ts.position.set(-(halfW(zW) + 0.4) / 2, S.yU(zW) + tW + 0.03, zW);
    }
    const Ts = J.stations.find((x) => x.id === 'comb-in').T;
    const fm = flameMat((u) => Ts + (S.T * 0.85 - Ts) * Math.min(1, u / 0.45) ** 0.6, S.zC0 - 0.1, S.zC1 - 0.8, J.at(S.zC1).V, 0.8);
    const fz = zs.filter((z) => z <= S.zC0 - 0.1 && z >= S.zC1 - 0.8);
    const fpos = [];
    const fidx = [];
    for (const z of fz) {
      const u = (S.zC0 - z) / (S.zC0 - S.zC1);
      const yl = S.yL(z) + 0.02;
      const yu = S.yU(z) - 0.02 - (1 - Math.min(1, u * 2)) * 0.5 * (S.yU(z) - S.yL(z));
      fpos.push(-W / 2 + 0.02, yl, z, W / 2 - 0.02, yl, z, -W / 2 + 0.02, yu, z, W / 2 - 0.02, yu, z);
    }
    for (let i = 1; i < fz.length; i++) {
      const a = (i - 1) * 4;
      const b = i * 4;
      fidx.push(a, b, b + 1, a, b + 1, a + 1, a + 2, b + 3, b + 2, a + 2, a + 3, b + 3, a, a + 2, b + 2, a, b + 2, b, a + 1, b + 1, b + 3, a + 1, b + 3, a + 3);
    }
    const fg = new THREE.BufferGeometry();
    fg.setAttribute('position', new THREE.Float32BufferAttribute(fpos, 3));
    fg.setIndex(fidx);
    fg.computeVertexNormals();
    addFlame(grp('combustor', 'scram'), fg, fm);
    // ramp shocks: planes from each ramp corner at the oblique-shock angle
    const corners = [J.zInlet, J.zInlet / 2];
    S.ramp.forEach((th, i) => {
      const sh = J.shocks[i];
      const z0 = corners[i];
      const y0 = S.yU(z0);
      // a shock leaves each ramp corner at the oblique-shock angle; drawn down to the cowl lip's height
      const a = S.ramp.slice(0, i).reduce((p, q) => p + q, 0) + sh.beta;
      const L = Math.min(8, Math.max(0.2, (y0 - S.yL(0)) / Math.sin(a)));
      const geo = new THREE.PlaneGeometry(W, L).translate(0, -L / 2, 0);
      const pm = add(grp('shock', 'shock'), mesh(geo, schlieren(rhoJump(sh.M * Math.sin(sh.beta)))), 'shock');
      pm.position.set(0, y0, z0);
      pm.quaternion.setFromUnitVectors(new V3(0, -1, 0), new V3(0, -Math.sin(a), -Math.cos(a)));
    });
    // The isolator's shock train: the combustor's back-pressure is held off by a train of oblique shocks reflecting
    // between the walls, each weaker than the last. Angles from the oblique-shock relation at the isolator Mach number
    // for a small effective deflection; drawn from the cowl lip to the combustor entry.
    {
      const Mi = J.stations.find((x) => x.id === 'comb-in')?.M ?? 2.2;
      let M = Mi * 1.15;
      let z = 0;
      let up = true;
      const legs = [];
      for (let k = 0; k < 12 && z > S.zC0; k++) {
        const beta = obliqueBeta(M, (4 * Math.PI) / 180);
        const yA = up ? S.yL(z) : S.yU(z);
        const h = S.yU(z) - S.yL(z);
        const dz = h / Math.tan(beta);
        const z1 = Math.max(S.zC0, z - dz);
        const yB = up ? S.yU(z1) : S.yL(z1);
        legs.push({z0: z, y0: yA, z1, y1: yB, jump: rhoJump(M * Math.sin(beta))});
        z = z1;
        up = !up;
        M = Math.max(1.2, M * 0.93);
      }
      J.shockTrain = legs;
      for (const L of legs) {
        const len = Math.hypot(L.z1 - L.z0, L.y1 - L.y0);
        const geo = new THREE.PlaneGeometry(W * 0.98, len).translate(0, len / 2, 0);
        const pm = add(grp('shock', 'shock'), mesh(geo, schlieren(L.jump * 1.4)), 'shock-train');
        pm.position.set(0, L.y0, L.z0);
        pm.quaternion.setFromUnitVectors(new V3(0, 1, 0), new V3(0, L.y1 - L.y0, L.z1 - L.z0).normalize());
      }
    }
    // hydrogen injected from each strut's base mixes into the air in a widening plume, burning as it goes
    for (let k = 0; k < S.struts; k++) {
      const x = -W / 2 + ((k + 1) * W) / (S.struts + 1);
      const z0 = S.zC0 - 0.05;
      const L = 0.9;
      const yC2 = (S.yU(z0) + S.yL(z0)) / 2;
      const pts = [];
      for (let i = 0; i <= 16; i++) {
        const u = i / 16;
        pts.push([0.012 + 0.07 * Math.sqrt(u), z0 - u * L]);
      }
      const fmP = flameMat(null, z0, z0 - L, J.at(z0).V, 0.6, null, (u) => [0.35 + 0.5 * u, 0.55 + 0.25 * u, 0.85 - 0.45 * u].map((c) => c * (0.6 - 0.3 * u)));
      const pl = addFlame(grp('combustor', 'scram'), revolve([[0.001, z0], ...pts, [0.001, z0 - L]], 32), fmP, 'fuel-plume');
      pl.position.set(x, yC2, 0);
    }
    J.particleWidth = W;
  }

  // ------------------------------------------------------------ accessory gearbox and its units, bleed, harness
  if (fam === 'turbofan' || fam === 'turbojet' || fam === 'turboprop') {
    const gA = grp('dress', 'agb', new V3(0, -0.5 * D, 0));
    const firstHP = J.modules.find((m) => m.spool === 'hp');
    const onFan = hw.agb === 'fan';
    const rA = onFan ? R * 1.09 : (J.combustor.r1 * 1.3) + 0.04 * D;
    const zA0 = onFan ? -J.fan.chord * 0.6 : firstHP.z0 + 0.05 * D;
    const len = onFan ? 0.5 * D : Math.max(0.25 * D, firstHP.z0 - firstHP.z1);
    const zc = zA0 - len / 2;
    const span = onFan ? 0.75 : 1.0;
    // the gearbox case: segments bent round the case underneath
    const nseg = 7;
    for (let k = 0; k < nseg; k++) {
      const a = -Math.PI / 2 + ((k - (nseg - 1) / 2) / nseg) * span;
      const bx = add(gA, mesh(roundedBox(rA * (span / nseg) * 1.12, 0.09 * D, len, 0.02 * D), mat.box), 'agb');
      bx.position.set((rA + 0.045 * D) * Math.cos(a), (rA + 0.045 * D) * Math.sin(a), zc);
      bx.rotation.z = a - Math.PI / 2;
    }
    // units on its rear face: starter, fuel pump with its fuel-control unit, generator, hydraulic and oil pumps
    const units = [['starter', 0.07, 0.16, -0.32], ['fuel-pump', 0.06, 0.14, -0.12], ['idg', 0.1, 0.2, 0.1], ['hyd-pump', 0.055, 0.12, 0.28], ['oil-pump', 0.045, 0.1, 0.42]];
    for (const [id, r, l, f] of units) {
      const a = -Math.PI / 2 + f * span;
      const ug = new THREE.Group();
      const body = mesh(new THREE.CylinderGeometry(r * D, r * D, l * D, 24).rotateX(Math.PI / 2), id === 'idg' ? mat.box : mat.aluminium);
      body.position.z = -l * D / 2;
      const fl = mesh(new THREE.CylinderGeometry(r * D * 1.18, r * D * 1.18, 0.012 * D, 24).rotateX(Math.PI / 2), M.forged);
      ug.add(body, fl);
      for (let j = 0; j < 3; j++) {
        const rib = mesh(new THREE.TorusGeometry(r * D * 1.01, 0.003 * D, 6, 32), M.forged);
        rib.position.z = -l * D * (0.25 + 0.25 * j);
        ug.add(rib);
      }
      ug.position.set((rA + 0.07 * D) * Math.cos(a), (rA + 0.07 * D) * Math.sin(a), zA0 - len);
      part(ug, id);
      gA.add(ug);
    }
    // tower shaft from the HP spool's front, radially down through a frame strut to the gearbox
    const tz = firstHP.z0 + 0.02 * D;
    const ts = add(gA, mesh(new THREE.CylinderGeometry(0.012 * D, 0.012 * D, rA - shaftR.hp * 1.4, 12).translate(0, -(rA + shaftR.hp * 1.4) / 2, 0), mat.shaft), 'tower-shaft');
    ts.position.z = onFan ? J.ogv.z - J.ogv.chord * 1.9 : tz;
    movers.push((t) => (ts.rotation.y = J.spools.hp.w * t));
    // the engine control unit on the fan case (turbofan) or the core: a finned box with its connectors and harness
    const eg = new THREE.Group();
    const ecu = mesh(roundedBox(0.16 * D, 0.06 * D, 0.22 * D, 0.012 * D), mat.box);
    eg.add(ecu);
    for (let j = 0; j < 7; j++) {
      const fin = mesh(new THREE.BoxGeometry(0.15 * D, 0.012 * D, 0.004 * D), mat.box);
      fin.position.set(0, 0.035 * D, -0.09 * D + j * 0.03 * D);
      eg.add(fin);
    }
    for (let j = 0; j < 3; j++) {
      const con = mesh(new THREE.CylinderGeometry(0.014 * D, 0.014 * D, 0.025 * D, 16).rotateZ(Math.PI / 2), mat.plastic);
      con.position.set(-0.09 * D, 0, -0.06 * D + j * 0.06 * D);
      eg.add(con);
    }
    const ea = -Math.PI / 2 + (onFan ? -0.75 : -1.0);
    const er = onFan ? R * 1.09 : rA;
    eg.position.set((er + 0.04 * D) * Math.cos(ea), (er + 0.04 * D) * Math.sin(ea), zc + 0.05 * D);
    eg.rotation.z = ea - Math.PI / 2;
    part(eg, 'fadec');
    gA.add(eg);
    // harness: two looms round the core with a lead to the engine control unit; temperature probes at the LP turbine
    const gD = grp('dress', 'core', new V3(0, 0.25 * D, 0));
    const hpcM = J.modules.find((m) => m.kind === 'hpc' || m.kind === 'compressor');
    for (const s of [hpcM.stages[0], hpcM.stages[hpcM.stages.length - 1]]) {
      add(gD, mesh(torusC(s.rt + 0.05 * D, 0.006 * D, 8, 128).translate(0, 0, s.z), mat.harness), 'harness');
      const nc = 6;
      const items = [];
      for (let k = 0; k < nc; k++) {
        const a = (k / nc) * TAU + 0.3;
        if (!keep(a)) continue;
        items.push([new V3((s.rt + 0.05 * D) * Math.cos(a), (s.rt + 0.05 * D) * Math.sin(a), s.z), new V3(Math.cos(a), Math.sin(a), 0)]);
      }
      const cl = instances(roundedBox(0.012 * D, 0.02 * D, 0.016 * D, 0.003 * D), mat.plastic, items);
      cl.frustumCulled = false;
      add(gD, cl, 'harness');
    }
    const turb = J.modules.find((m) => m.kind === 'lpt' || m.kind === 'pt') ?? J.modules.find((m) => m.kind === 'hpt');
    const tr = turb.stages[0].rt + 0.015 * D;
    const probes = [];
    for (let k = 0; k < 8; k++) {
      const a = (k / 8) * TAU + 0.2;
      if (!keep(a)) continue;
      probes.push([new V3((tr + 0.02 * D) * Math.cos(a), (tr + 0.02 * D) * Math.sin(a), turb.z0 - 0.01 * D), new V3(Math.cos(a), Math.sin(a), 0)]);
    }
    const pr = instances(new THREE.CylinderGeometry(0.008 * D, 0.008 * D, 0.06 * D, 8), M.steel, probes);
    pr.frustumCulled = false;
    add(gD, pr, 'egt-probe');
    add(gD, mesh(torusC(tr + 0.05 * D, 0.004 * D, 6, 128).translate(0, 0, turb.z0 - 0.01 * D), mat.harness), 'egt-probe');
    // bleed: two ducts off the compressor case, each through a valve, running aft
    const sB = hpcM.stages[Math.floor(hpcM.stages.length * 0.6)];
    for (const a of [Math.PI * 0.18, Math.PI * 0.82]) {
      const c = new V3(Math.cos(a), Math.sin(a), 0);
      const r0 = sB.rt + 0.02 * D;
      const p0 = c.clone().multiplyScalar(r0).setZ(sB.z);
      const p1 = c.clone().multiplyScalar(r0 + 0.07 * D).setZ(sB.z - 0.03 * D);
      const p2 = c.clone().multiplyScalar(r0 + 0.1 * D).setZ(sB.z - 0.2 * D);
      const p3 = c.clone().multiplyScalar(J.combustor.r1 * 1.25 + 0.06 * D).setZ(J.combustor.z1);
      add(gD, mesh(tube([p0, p1, p2, p3], 0.018 * D, false, 48), mat.pipe), 'bleed');
      const v = add(gD, mesh(new THREE.CylinderGeometry(0.03 * D, 0.03 * D, 0.05 * D, 20), mat.box), 'bleed');
      v.position.copy(p2);
      v.quaternion.setFromUnitVectors(new V3(0, 1, 0), p3.clone().sub(p1).normalize());
      const act = add(gD, mesh(roundedBox(0.03 * D, 0.03 * D, 0.04 * D, 0.006 * D), mat.plastic), 'bleed');
      act.position.copy(p2).addScaledVector(c, 0.035 * D);
    }
  }

  // ------------------------------------------------------------ mounts and the display stand
  {
    const g = grp('stand', 'stand', new V3(0, -0.6 * D, 0));
    const box = new THREE.Box3();
    root.updateMatrixWorld(true);
    // sized on the casings: the propeller and the gas reach far past them
    for (const id of ['casing', 'nacelle']) box.expandByObject(layer[id]);
    const yB = box.min.y - 0.12 * D;
    const z0 = box.max.z - 0.15 * (box.max.z - box.min.z);
    const z1 = box.min.z + 0.2 * (box.max.z - box.min.z);
    const wid = Math.max(0.6 * D, 0.5 * (box.max.x - box.min.x));
    const tubeT = 0.045 * D;
    const rail = (a, b) => {
      const d = a.distanceTo(b);
      const m = add(g, mesh(roundedBox(tubeT, tubeT, d, tubeT * 0.2), mat.stand), 'stand');
      m.position.copy(a).lerp(b, 0.5);
      m.lookAt(b);
      return m;
    };
    if (fam === 'scramjet') {
      // a display plinth: four columns to pads under the body, outboard of the sidewalls, so nothing stands in the
      // flow path or the exhaust; each pad is tilted to the underside's slope at that point
      const S = J.scram;
      const zF = J.zInlet - 1.8;
      const zR = S.zN1 + 1.2;
      const slab = add(g, mesh(roundedBox(1.3, 0.05, zF - zR + 0.7, 0.02), mat.plastic), 'stand');
      slab.position.set(0, yB, (zF + zR) / 2);
      for (const [z, xc] of [[zF, 0.42], [zR, 0.6]]) {
        const s = (S.yU(z + 0.01) - S.yU(z - 0.01)) / 0.02;
        const yP = S.yU(z) - 0.02;
        for (const sx of [-1, 1]) {
          const h = yP - (yB + 0.025);
          const c = add(g, mesh(new THREE.CylinderGeometry(0.035, 0.05, h, 24), mat.stand), 'stand');
          c.position.set(sx * xc, yB + 0.025 + h / 2, z);
          const pad = add(g, mesh(roundedBox(0.14, 0.025, 0.22, 0.008), mat.plastic), 'stand');
          pad.position.set(sx * xc, yP + 0.0075, z);
          pad.rotation.x = -Math.atan(s);
        }
      }
      for (const sx of [-1, 1]) for (const z of [zF + 0.28, zR - 0.28]) {
        const f = add(g, mesh(new THREE.CylinderGeometry(0.045, 0.055, 0.03, 20), mat.plastic), 'stand');
        f.position.set(sx * 0.58, yB - 0.04, z);
      }
    } else {
      for (const sx of [-1, 1]) rail(new V3(sx * wid / 2, yB, z0), new V3(sx * wid / 2, yB, z1));
      for (const z of [z0, z1, (z0 + z1) / 2]) rail(new V3(-wid / 2, yB, z), new V3(wid / 2, yB, z));
      // uprights from the frame to a saddle under the engine, front and rear
      const saddleAt = (z) => {
        const st = J.at(z, J.coreStations);
        let r = st.rt * 1.06 + 0.02 * D;
        if (J.bypass && z > J.bypass.z1) r = R * 1.1;
        return r;
      };
      for (const z of [z0 - 0.05 * D, z1 + 0.05 * D]) {
        const r = saddleAt(z);
        const yTop = -r;
        for (const sx of [-1, 1]) rail(new V3(sx * wid / 2, yB, z), new V3(sx * r * 0.55, yTop - 0.02 * D, z));
        const sad = add(g, mesh(new THREE.TorusGeometry(r, tubeT * 0.45, 8, 48, Math.PI * 0.6).rotateZ(-Math.PI * 0.8), mat.stand), 'stand');
        sad.position.z = z;
      }
      // feet
      for (const sx of [-1, 1]) for (const z of [z0, z1]) {
        const f = add(g, mesh(new THREE.CylinderGeometry(0.05 * D, 0.06 * D, 0.03 * D, 20), mat.plastic), 'stand');
        f.position.set(sx * wid / 2, yB - tubeT / 2 - 0.015 * D, z);
      }
    }
  }

  // ------------------------------------------------------------ the gas, as streaklines
  // Each tracer is drawn as a short trail: its positions over the last few instants of its flight, fading. Along the
  // axis it moves at the station speeds; round the axis it turns by the swirl angle Euler's equation gives (kin.js),
  // so the trails twist through each rotor and straighten in each stator. Turbulence is a smooth random displacement
  // whose size is the local turbulence intensity times the annulus height (drawn three times larger than life so the
  // eddies read at this scale). All of it is a pure function of time.
  const flows = [];
  const K = 12;
  {
    const g = grp('flow', 'flow');
    const stream = (key, path, sts, n, angle0, angle1) => {
      const pos = new Float32Array(n * K * 2 * 3);
      const col = new Float32Array(n * K * 2 * 4);
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
      geo.setAttribute('color', new THREE.BufferAttribute(col, 4).setUsage(THREE.DynamicDrawUsage));
      const lm = new THREE.LineBasicMaterial({vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending});
      const lines = new THREE.LineSegments(geo, lm);
      lines.frustumCulled = false;
      add(g, lines, 'flow', {stream: key});
      const ph = new Float32Array(n);
      const th = new Float32Array(n);
      const uu = new Float32Array(n);
      const nz = new Float32Array(n * 6);
      // deterministic spread (golden-ratio sequences) and per-tracer eddy phases, so frames are reproducible
      for (let i = 0; i < n; i++) {
        ph[i] = (i * 0.6180339887) % 1;
        th[i] = angle0 + (angle1 - angle0) * ((i * 0.7548776662) % 1);
        uu[i] = 0.12 + 0.76 * ((i * 0.569840291) % 1);
        for (let j = 0; j < 6; j++) nz[i * 6 + j] = ((i * (0.3819660113 + j * 0.1414213562)) % 1) * TAU;
      }
      flows.push({lines, pos, col, geo, path, sts, n, ph, th, uu, nz, key});
    };
    const a0 = -0.2;
    const a1 = Math.PI / 2 + 0.2;
    const nT = (n) => Math.round(n * DET);
    if (fam === 'scramjet') stream('core', J.paths.core, J.coreStations, nT(700), 0, 1);
    else stream('core', J.paths.core, J.coreStations, nT(fam === 'turbofan' ? 520 : 700), a0, a1);
    if (J.paths.bypass) stream('bypass', J.paths.bypass, J.bypassStations, nT(520), a0, a1);
  }
  const cTmp = new THREE.Color();
  /** temperature to colour: cold air blue-grey, warming through white to the flame's orange */
  const tempColor = (T, out) => {
    if (T < 600) return out.setRGB(0.45 + (T - 200) / 1600, 0.65 + (T - 200) / 1600, 1.0);
    if (T < 1100) {
      const u = (T - 600) / 500;
      return out.setRGB(0.75 + 0.25 * u, 0.9 - 0.15 * u, 1.0 - 0.6 * u);
    }
    return blackbody(Math.min(2400, T), out).multiplyScalar(1.3);
  };
  // a smooth random signal: three incommensurate sines per tracer and axis, unit rms
  const eddy = (nz, o, x) => (Math.sin(x * 1.0 + nz[o]) + 0.62 * Math.sin(x * 2.63 + nz[o + 1]) + 0.38 * Math.sin(x * 6.07 + nz[o + 2])) * 0.84;
  const tracer = (F, i, tt, out) => {
    const {path, sts} = F;
    const tau = tt + F.ph[i] * path.T;
    const z = path.zAt(tau);
    const st = J.at(z, sts);
    const h = st.rt - st.rh;
    const tu = 3 * J.tu(z);
    // the energetic eddies turn over a few times per transit (fine scales ride on top), on the tracer's own clock
    const x = (mod(tau, path.T) / path.T) * 9;
    const r = st.rh + h * Math.min(0.97, Math.max(0.03, F.uu[i] + tu * eddy(F.nz, i * 6, x)));
    if (fam === 'scramjet') {
      out.set((F.th[i] - 0.5) * J.particleWidth * 0.9, r, z);
    } else {
      const a = F.th[i] + path.thAt(z) + (tu * h * eddy(F.nz, i * 6 + 3, x * 1.3)) / Math.max(0.02 * D, r);
      out.set(r * Math.cos(a), r * Math.sin(a), z);
    }
    return st;
  };
  // flow colour: static temperature (default), axial speed or total pressure. Speed and pressure use viridis, which
  // reads in greyscale and to the colour-blind; temperature keeps its physical cold-blue to flame scale.
  let flowMode = 'temperature';
  const ranges = {V: Math.max(...J.stations.map((x) => x.V || 0)), P: Math.max(...J.stations.map((x) => x.Pt || 0))};
  const VIRIDIS = [[0.267, 0.005, 0.329], [0.229, 0.322, 0.546], [0.128, 0.567, 0.551], [0.369, 0.789, 0.383], [0.993, 0.906, 0.144]];
  const ramp5 = (stops, u, out) => {
    u = Math.min(1, Math.max(0, u)) * (stops.length - 1);
    const i = Math.min(stops.length - 2, Math.floor(u));
    const f = u - i;
    return out.setRGB(...stops[i].map((c, j) => c + (stops[i + 1][j] - c) * f));
  };
  const flowColor = (st, out) => {
    if (flowMode === 'velocity') return ramp5(VIRIDIS, st.V / ranges.V, out);
    if (flowMode === 'pressure') return ramp5(VIRIDIS, st.Pt / ranges.P, out);
    return tempColor(st.T, out);
  };
  const pA = new V3();
  const pB = new V3();
  const updateFlow = (t) => {
    for (const F of flows) {
      const {pos, col, n, path} = F;
      // a trail spans about 1/30 of the transit, in K pieces
      const dt = path.T / 30 / K;
      let o = 0;
      let c = 0;
      for (let i = 0; i < n; i++) {
        let st = tracer(F, i, t, pA);
        for (let k = 0; k < K; k++) {
          const z0 = pA.z;
          tracer(F, i, t - (k + 1) * dt, pB);
          // a tracer that has just wrapped from the exit back to the inlet leaves no streak across the engine
          const wrap = pB.z < z0 - 0.2 * D;
          flowColor(st, cTmp);
          const f0 = wrap ? 0 : 0.75 * (1 - k / K);
          const f1 = wrap ? 0 : 0.75 * (1 - (k + 1) / K);
          pos[o++] = pA.x;
          pos[o++] = pA.y;
          pos[o++] = pA.z;
          pos[o++] = pB.x;
          pos[o++] = pB.y;
          pos[o++] = pB.z;
          col[c++] = cTmp.r * f0;
          col[c++] = cTmp.g * f0;
          col[c++] = cTmp.b * f0;
          col[c++] = f0;
          col[c++] = cTmp.r * f1;
          col[c++] = cTmp.g * f1;
          col[c++] = cTmp.b * f1;
          col[c++] = f1;
          pA.copy(pB);
          if (k === 0) st = J.at(pB.z, F.sts);
        }
      }
      F.geo.attributes.position.needsUpdate = true;
      F.geo.attributes.color.needsUpdate = true;
    }
  };

  // ------------------------------------------------------------ glow twins for everything that emits light
  const glowers = [];
  for (const o of hot) {
    if (o.userData.spark) {
      glowers.push(o);
      continue;
    }
    const tm = new THREE.MeshBasicMaterial({
      color: new THREE.Color(o.material.emissive).multiplyScalar(o.material.emissiveIntensity * 0.16),
      depthWrite: false,
      transparent: true,
      opacity: 0.8,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -4,
      side: THREE.DoubleSide,
    });
    if (o.material.userData.cut) cut(tm);
    const twin = new THREE.Mesh(o.geometry, tm);
    o.add(twin);
    glowers.push(twin);
  }

  // ------------------------------------------------------------ pose, cut, explode, layers
  // ------------------------------------------------------------ the thermal analysis view
  // Every solid part recoloured by the gas total temperature at its axial station (the cycle's T3, T4, T5 and the
  // rest, interpolated along the gas path; the bypass duct at the fan-exit temperature), on the magma scale.
  const zA0 = J.zInlet;
  const zA1 = J.zEnd;
  const tTex = (() => {
    const N = 256;
    const d = new Float32Array(N * 4);
    for (let i = 0; i < N; i++) {
      const z = zA0 + ((zA1 - zA0) * i) / (N - 1);
      d.set([J.at(z).Tt, 0, 0, 1], i * 4);
    }
    const t = new THREE.DataTexture(d, N, 1, THREE.RGBAFormat, THREE.FloatType);
    t.magFilter = t.minFilter = THREE.LinearFilter;
    t.needsUpdate = true;
    return t;
  })();
  const Tmin = Math.min(...J.stations.map((x) => x.Tt));
  const Tmax = Math.max(...J.stations.map((x) => x.Tt), J.afterburner?.T ?? 0);
  const T13 = J.bypassStations ? J.bypassStations[2].Tt : 0;
  const thermalMat = new THREE.MeshLambertMaterial({side: THREE.DoubleSide});
  thermalMat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, {uTT: {value: tTex}, uZ0: {value: zA0}, uZ1: {value: zA1}, uTmin: {value: Tmin}, uTmax: {value: Tmax}, uRs: {value: J.bypass ? J.splitR : 1e9}, uT13: {value: T13}});
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;').replace('#include <project_vertex>', `#include <project_vertex>
      { vec4 wp = vec4(transformed, 1.0);
        #ifdef USE_INSTANCING
          wp = instanceMatrix * wp;
        #endif
        vWP = wp.xyz; }`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
      varying vec3 vWP; uniform sampler2D uTT; uniform float uZ0, uZ1, uTmin, uTmax, uRs, uT13;
      vec3 magma(float t) {
        const vec3 c0 = vec3(-0.002136485053939582, -0.000749655052795221, -0.005386127855323933);
        const vec3 c1 = vec3(0.2516605407371642, 0.6775232436837668, 2.494026599312351);
        const vec3 c2 = vec3(8.353717279216625, -3.577719514958484, 0.3144679030132573);
        const vec3 c3 = vec3(-27.66873308576866, 14.26473078096533, -13.64921318813922);
        const vec3 c4 = vec3(52.17613981234068, -27.94360607168351, 12.94416944238394);
        const vec3 c5 = vec3(-50.76852536473588, 29.04658282127291, 4.23415299384598);
        const vec3 c6 = vec3(18.65570506591883, -11.48977351997711, -5.601961508734096);
        return c0 + t * (c1 + t * (c2 + t * (c3 + t * (c4 + t * (c5 + t * c6)))));
      }`).replace('vec4 diffuseColor = vec4( diffuse, opacity );', `
      float Tz = texture2D(uTT, vec2(clamp((vWP.z - uZ0) / (uZ1 - uZ0), 0.0, 1.0), 0.5)).r;
      if (length(vWP.xy) > uRs && vWP.z < 0.0 && uT13 > 0.0) Tz = uT13;
      vec4 diffuseColor = vec4(magma(0.08 + 0.88 * clamp((Tz - uTmin) / (uTmax - uTmin), 0.0, 1.0)), 1.0);`);
  };
  const swapped = [];
  const setThermal = (on) => {
    for (const [o, m] of swapped) o.material = m;
    swapped.length = 0;
    if (!on) return;
    root.traverse((o) => {
      if (!o.isMesh || o.userData.spark || !o.material || o.material.transparent || o.material.isShaderMaterial || o.material.isMeshBasicMaterial) return;
      swapped.push([o, o.material]);
      o.material = thermalMat;
    });
  };

  // ------------------------------------------------------------ thermal growth, exaggerated
  // Each module grows radially by alpha * (T - 293 K), taking alpha = 13e-6 /K (nickel and titanium alloys are 9 to
  // 14e-6) and T the module's mean gas temperature; the slider multiplies it so millimetres become visible.
  const growK = {};
  for (const m of J.modules) growK[m.kind] = ((m.Tt0 ?? 300) + (m.Tt1 ?? 300)) / 2;
  if (J.combustor) growK.comb = J.combustor.T * 0.7;
  growK.nozzle = J.stations.find((x) => x.id === 'lpt-exit')?.Tt ?? 300;
  const setGrowth = (k) => {
    for (const [id, g] of groups) {
      const key = id.split('/')[1];
      if (!(key in growK)) continue;
      const s = 1 + 13e-6 * (growK[key] - 293) * k;
      g.scale.set(s, s, 1);
    }
  };
  let playRate = 0;
  const setPlayRate = (r) => {
    playRate = r;
    for (const b of blurs) {
      const sp = J.spools[b.spool] ?? {w: 0};
      // pitches turned per frame at 60 fps
      const pitches = (sp.w * r * b.n) / (60 * TAU);
      const u = Math.min(1, Math.max(0, (pitches - 0.35) / 1.15));
      b.m.opacity = u * b.solidity;
      b.d.visible = u > 0.01;
      if (b.row) b.row.visible = u < 0.999;
    }
  };
  const update = (t) => {
    vib.uVT.value = performance.now() / 1000;
    for (const k of Object.keys(spinT)) {
      const s = spinT[k];
      const a = mod(s.w * t, TAU);
      for (const [o, sign] of s.objs) o.rotation.z = a * sign;
    }
    for (const f of movers) f(t);
    for (const m of flames) m.uniforms.uT.value = t;
    if (layer.flow.visible) updateFlow(t);
  };
  // the cut is part of the geometry: a different cut is a rebuild (see live.js)
  const setCut = () => null;
  const m4x = new THREE.Matrix4();
  const qx = new THREE.Quaternion();
  const zA = new V3(0, 0, 1);
  const one = new V3(1, 1, 1);
  const setExplode = (e) => {
    for (const {g, v} of explodable) g.position.copy(v).multiplyScalar(e);
    // blade rows lift radially out of their disc slots, so the roots show
    const lift = Math.max(0, e - 0.15) * 0.06 * D;
    for (const R of radialRows) {
      if (R.ring) {
        R.m.scale.set(1 + lift / R.r, 1 + lift / R.r, 1);
        continue;
      }
      for (let k = 0; k < R.n; k++) {
        const a = (k / R.n) * TAU;
        qx.setFromAxisAngle(zA, a);
        R.m.setMatrixAt(k, m4x.compose(new V3(-Math.sin(a) * lift, Math.cos(a) * lift, 0), qx, one));
      }
      R.m.instanceMatrix.needsUpdate = true;
    }
  };
  const setLayer = (id, on) => (layer[id].visible = on);
  // shadows: the solid parts cast and receive; small parts and the gas do not
  root.traverse((o) => {
    if (!o.isMesh) return;
    const m = o.material;
    if (m.transparent || m.isMeshBasicMaterial) return;
    o.receiveShadow = true;
    if (!o.geometry.boundingSphere) o.geometry.computeBoundingSphere();
    o.castShadow = o.isInstancedMesh || o.geometry.boundingSphere.radius > 0.08 * D;
  });

  // ------------------------------------------------------------ section caps
  // Every cut casing gets a solid face at each cut plane, filled from its own profile and shaded by engineering
  // section convention: hatched at 45 degrees, tinted by material class (aluminium grey, titanium blue-grey, nickel
  // and steel warm, ceramics and coatings cream, composites dark, liners green-grey, paint white).
  const CAP = {alCast: '#a7afb8', alMachined: '#b9c0c7', ti64: '#8fa6c0', inconel718: '#b98a63', stainlessHot: '#a8805e', steel: '#9ea4aa',
    cmsxTbc: '#d2c39d', cmsxFilm: '#d2c39d', tbcEffusion: '#d2c39d', cmc: '#6d6a64', cfrp: '#3b3f45', paintWhite: '#e4e6e8', paintGrey: '#7c838b',
    paintBlack: '#2e3136', honeycomb: '#8d9a7c', acoustic: '#8d9a7c', coolPanel: '#c48a5c'};
  const capMats = {};
  const capMat = (alloyName) => (capMats[alloyName] ||= new THREE.ShaderMaterial({
    uniforms: {uC: {value: new THREE.Color(CAP[alloyName] ?? '#9aa0a6')}, uS: {value: 70 / D}},
    vertexShader: 'varying vec3 vP; void main() { vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: 'uniform vec3 uC; uniform float uS; varying vec3 vP; void main() { float h = fract((vP.z + length(vP.xy)) * uS); float line = 1.0 - smoothstep(0.0, 0.12, h) * (1.0 - smoothstep(0.88, 1.0, h)); gl_FragColor = vec4(uC * (0.55 + 0.35 * (1.0 - line)), 1.0); }',
    side: THREE.DoubleSide,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -2,
  }));
  if (KEEP) {
    const caps = [];
    root.traverse((o) => {
      const pr = o.isMesh && o.geometry?.userData?.profile;
      const m = o.material;
      if (!pr || !m?.userData?.cut || m.transparent || m.isShaderMaterial || pr.length < 3) return;
      const a0 = pr[0];
      const a1 = pr[pr.length - 1];
      if (Math.hypot(a0[0] - a1[0], a0[1] - a1[1]) > 1e-6 && pr.length < 4) return;
      caps.push(o);
    });
    for (const o of caps) {
      const pr = o.geometry.userData.profile;
      const sh = new THREE.Shape(pr.map(([r, z]) => new THREE.Vector2(r, z)));
      let geo;
      try {
        geo = new THREE.ShapeGeometry(sh, 2);
      } catch {
        continue;
      }
      if (!geo.attributes.position.count) continue;
      for (const a of [KEEP[0], KEEP[0] + KEEP[1]]) {
        const g = geo.clone();
        const p = g.attributes.position;
        for (let i = 0; i < p.count; i++) {
          const r = p.getX(i);
          const z = p.getY(i);
          p.setXYZ(i, r * Math.cos(a), r * Math.sin(a), z);
        }
        p.needsUpdate = true;
        g.computeVertexNormals();
        const c = new THREE.Mesh(g, capMat(o.material.userData.alloy));
        c.userData.cap = true;
        o.add(c);
      }
    }
  }

  return {root, update, setCut, setExplode, setLayer, glowers, layers: layer, info: {Tmin, Tmax},
    // the glow pass sees large flames at a third of their strength, so their bloom does not spill past the casings
    setGlowPass: (on) => {
      for (const m of flames) m.uniforms.uG.value = on ? 0.35 : 1;
    },
    setFlowColor: (m) => (flowMode = m), setThermal, setGrowth, setPlayRate,
    setVibration: (mode, amp) => {
      vib.uMode.value = mode;
      vib.uAmp.value = amp * 0.03 * D;
    }, flowRange: ranges};
}

/** merge several non-indexed geometries' positions and normals into one */
function mergeGeos(geos) {
  const parts = geos.map((g) => (g.index ? g.toNonIndexed() : g));
  const n = parts.reduce((a, g) => a + g.attributes.position.count, 0);
  const pos = new Float32Array(n * 3);
  const nor = new Float32Array(n * 3);
  let o = 0;
  for (const g of parts) {
    pos.set(g.attributes.position.array, o * 3);
    nor.set(g.attributes.normal.array, o * 3);
    o += g.attributes.position.count;
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  return out;
}

// Surfaces and detailed part geometry for the engine: procedural textures (cast grain, machined brushing, crinkle
// paint), physically based materials, black-body glow, and the part shapes that need more than a box: a hollow
// piston with pin bosses and rings, an I-beam rod with a bolted cap, a spark plug, a poly-V pulley, hex bolts,
// a head gasket and roller-chain plates. Everything is deterministic: no Math.random, so frames are reproducible.
import * as THREE from 'three';
import {alloy} from '../shared/alloys.js';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';

const V2 = THREE.Vector2;

/** a box with every edge filleted to radius r, as castings and mouldings are */
export const roundedBox = (w, h, d, r, seg = 2) => new RoundedBoxGeometry(w, h, d, seg, Math.min(r, 0.49 * Math.min(w, h, d)));

// ------------------------------------------------------------ deterministic noise
const hash = (x, y, s) => {
  let h = (x * 374761393 + y * 668265263 + s * 982451653) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
};
const valueNoise = (x, y, s) => {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const fx = x - xi;
  const fy = y - yi;
  const u = fx * fx * (3 - 2 * fx);
  const v = fy * fy * (3 - 2 * fy);
  const a = hash(xi, yi, s);
  const b = hash(xi + 1, yi, s);
  const c = hash(xi, yi + 1, s);
  const d = hash(xi + 1, yi + 1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
};
const canvasTex = (w, h, px, repeat = 1) => {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  const g = c.getContext('2d');
  const img = g.createImageData(w, h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const v = Math.max(0, Math.min(255, Math.round(px(x, y) * 255)));
    const i = (y * w + x) * 4;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat, repeat);
  return t;
};

/** shared textures, made once per page */
let TEX = null;
const textures = () => {
  if (TEX) return TEX;
  // sand-cast grain: two octaves of value noise around a mid roughness
  const cast = canvasTex(256, 256, (x, y) => 0.55 + 0.25 * (valueNoise(x / 6, y / 6, 1) - 0.5) + 0.15 * (valueNoise(x / 1.7, y / 1.7, 2) - 0.5), 3);
  // machined: fine streaks along u (lathe and cylinder u runs round the part)
  const brushed = canvasTex(256, 64, (x, y) => 0.32 + 0.22 * (valueNoise(x / 0.8, y / 24, 3) - 0.5) + 0.06 * (valueNoise(x / 9, y / 3, 4) - 0.5), 1);
  // crinkle paint: sharp, dense bumps
  const crinkle = canvasTex(256, 256, (x, y) => {
    const n = valueNoise(x / 2.2, y / 2.2, 5);
    return Math.pow(n, 2.2);
  }, 4);
  TEX = {cast, brushed, crinkle};
  return TEX;
};

/** physically based materials for the engine */
export function makeMaterials(hw) {
  const T = textures();
  const phys = (o) => new THREE.MeshPhysicalMaterial({envMapIntensity: 1, ...o});
  // Ground finish rather than mirror: a spinning part under a near-mirror finish sweeps the studio's light panels
  // across itself in hard flashes. A floor on roughness and a gentler environment keep the sheen without the strobe.
  const machined = (color, rough = 0.3, aniso = 0.6) =>
    phys({color, metalness: 1, roughness: Math.max(0.42, rough + 0.16), roughnessMap: T.brushed, anisotropy: aniso * 0.5, envMapIntensity: 0.7});
  const cast = (color, rough = 0.62) => phys({color, metalness: 0.55, roughness: rough, roughnessMap: T.cast, bumpMap: T.cast, bumpScale: 0.6});
  // sand-cast aluminium as it leaves the foundry: a metal, dull and grainy, never chrome
  const castAlu = (color) => phys({color, metalness: 0.6, roughness: 0.58, roughnessMap: T.cast, bumpMap: T.cast, bumpScale: 0.22, envMapIntensity: 1});
  return {
    steel: alloy('steel', {repeat: [1, 6]}),
    forged: phys({color: '#7f868f', metalness: 1, roughness: 0.48, roughnessMap: T.cast, bumpMap: T.cast, bumpScale: 0.3}),
    alu: cast('#d4d7db', 0.5),
    aluMachined: machined('#e3e5e8', 0.26, 0.4),
    bronze: phys({color: '#c4955a', metalness: 1, roughness: 0.44}),
    black: phys({color: '#22252a', metalness: 0.2, roughness: 0.55}),
    rubber: alloy('rubber'),
    vin: machined('#8bb8ea', 0.3, 0.3),
    vex: machined('#d79466', 0.32, 0.3),
    spring: phys({color: '#9aa3ad', metalness: 1, roughness: 0.42, clearcoat: 0.3, clearcoatRoughness: 0.4}),
    cam: machined('#c3c9d0', 0.22, 0.7),
    chain: machined('#aab1b9', 0.3, 0.3),
    pin: machined('#e1e4e8', 0.18, 0.2),
    bolt: phys({color: '#7c8188', metalness: 1, roughness: 0.46}),
    header: alloy('stainlessHot', {repeat: [1, 8]}),
    turbine: cast('#565a61', 0.55),
    compressor: cast('#c7cacf', 0.4),
    plenum: phys({color: '#33373e', metalness: 0.3, roughness: 0.5, roughnessMap: T.cast, bumpMap: T.cast, bumpScale: 0.3}),
    filter: phys({color: '#1d3350', metalness: 0.3, roughness: 0.4, clearcoat: 0.7, clearcoatRoughness: 0.25}),
    gasket: phys({color: '#3b3f46', metalness: 0.9, roughness: 0.4}),
    ceramic: phys({color: '#f1ede4', metalness: 0, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.08}),
    coil: phys({color: '#1f2226', metalness: 0.1, roughness: 0.45, clearcoat: 0.5}),
    // the cam cover in the maker's paint, crinkle-finished under a clear coat
    cover: phys({color: hw.cover_color || '#2a2d33', metalness: 0.2, roughness: 0.55, bumpMap: T.crinkle, bumpScale: 1.2, clearcoat: 0.8, clearcoatRoughness: 0.4}),
    oil: phys({color: '#9a6a18', metalness: 0, roughness: 0.08, transmission: 0, transparent: true, opacity: 0.38, depthWrite: false, clearcoat: 1}),
    castShell: (color) => {
      const m = castAlu(color);
      m.userData.wearRole = 'cast';
      return m;
    },
  };
}

// ------------------------------------------------------------ black-body light
/** sRGB colour of a black body at T kelvin (Tanner Helland's fit to the Planck locus, good from 1000 K to 40000 K) */
export function blackbody(T, out = new THREE.Color()) {
  const t = Math.max(1000, Math.min(40000, T)) / 100;
  let r;
  let g;
  let b;
  if (t <= 66) {
    r = 255;
    g = 99.4708025861 * Math.log(t) - 161.1195681661;
    b = t <= 19 ? 0 : 138.5177312231 * Math.log(t - 10) - 305.0447927307;
  } else {
    r = 329.698727446 * Math.pow(t - 60, -0.1332047592);
    g = 288.1221695283 * Math.pow(t - 60, -0.0755148492);
    b = 255;
  }
  const c = (v) => Math.max(0, Math.min(255, v)) / 255;
  return out.setRGB(c(r), c(g), c(b), THREE.SRGBColorSpace);
}
/** steel starts to glow visibly at the Draper point; above it, radiance rises as T^4 */
export const DRAPER_K = 798;
export const glowIntensity = (T, ref = 1300) => (T <= DRAPER_K ? 0 : Math.pow((T - DRAPER_K) / (ref - DRAPER_K), 4));

// ------------------------------------------------------------ part geometry
const lathe = (pts, seg = 40) => new THREE.LatheGeometry(pts.map(([x, y]) => new V2(x, y)), seg);

/** hollow piston: crown at y = 0, skirt down to -0.7B, a 0.06B wall, a crown 0.12B thick */
export function pistonGeometry(B, diesel = false) {
  const R = 0.495 * B;
  const r = R - 0.06 * B;
  // a diesel's piston carries the combustion chamber: a re-entrant bowl with a central pip
  const crown = diesel
    ? [[0, -0.035 * B], [0.07 * B, -0.075 * B], [0.17 * B, -0.12 * B], [0.25 * B, -0.11 * B], [0.29 * B, -0.07 * B], [0.27 * B, -0.03 * B], [0.31 * B, 0]]
    : [[0, 0]];
  const under = diesel ? -0.17 * B : -0.12 * B;
  const g = lathe([
    ...crown, [R - 0.01 * B, 0], [R, -0.01 * B], [R, -0.05 * B], [R - 0.014 * B, -0.055 * B], [R - 0.014 * B, -0.075 * B], [R, -0.08 * B],
    [R, -0.11 * B], [R - 0.014 * B, -0.115 * B], [R - 0.014 * B, -0.135 * B], [R, -0.14 * B], [R, -0.17 * B], [R - 0.016 * B, -0.175 * B],
    [R - 0.016 * B, -0.2 * B], [R, -0.205 * B], [R, -0.7 * B], [r, -0.7 * B], [r, under], [0, under],
  ], 64);
  return g;
}
/** the three rings (two compression, one oil) as tori sitting in the grooves */
export function ringGeometries(B) {
  const R = 0.495 * B;
  return [-0.065, -0.125, -0.19].map((y, i) => new THREE.TorusGeometry(R - 0.004 * B, i === 2 ? 0.012 * B : 0.009 * B, 6, 48).rotateX(Math.PI / 2).translate(0, y * B, 0));
}
/** pin bosses inside the skirt, on the wrist pin axis (z) */
export function bossGeometry(B, crownH) {
  const g = new THREE.CylinderGeometry(0.15 * B, 0.15 * B, 0.2 * B, 20).rotateX(Math.PI / 2);
  const a = g.clone().translate(0, -crownH, 0.37 * B);
  const b = g.clone().translate(0, -crownH, -0.37 * B);
  return [a, b];
}

/** I-beam connecting rod laid along +y from the big end (0) to the small end (L), thickness t along z: a thin web,
 * full-thickness flanges along both edges, and full-thickness eyes. Returns one merged geometry. */
export function rodGeometry(B, L, t) {
  const rb = 0.34 * B;
  const rs = 0.17 * B;
  const Rb = rb + 0.06 * B;
  const Rs = rs + 0.05 * B;
  const wb = 0.24 * B;
  const ws = 0.12 * B;
  const outline = () => {
    const s = new THREE.Shape();
    s.absarc(0, 0, Rb, Math.PI - 0.5, 2 * Math.PI + 0.5, false);
    s.lineTo(wb, rb);
    s.lineTo(ws, L - rs);
    s.absarc(0, L, Rs, -0.35, Math.PI + 0.35, false);
    s.lineTo(-ws, L - rs);
    s.lineTo(-wb, rb);
    s.closePath();
    const big = new THREE.Path();
    big.absarc(0, 0, rb, 0, Math.PI * 2, true);
    const small = new THREE.Path();
    small.absarc(0, L, rs * 0.72, 0, Math.PI * 2, true);
    s.holes.push(big, small);
    return s;
  };
  const ext = (shape, d) => new THREE.ExtrudeGeometry(shape, {depth: d, bevelEnabled: false, curveSegments: 20}).translate(0, 0, -d / 2);
  const ring = (cy, R, r) => {
    const s = new THREE.Shape();
    s.absarc(0, cy, R, 0, Math.PI * 2, false);
    const h = new THREE.Path();
    h.absarc(0, cy, r, 0, Math.PI * 2, true);
    s.holes.push(h);
    return ext(s, t);
  };
  const flange = (x0, y0, x1, y1) => {
    const len = Math.hypot(x1 - x0, y1 - y0);
    return new THREE.BoxGeometry(0.05 * B, len, t)
      .rotateZ(-Math.atan2(x1 - x0, y1 - y0))
      .translate((x0 + x1) / 2, (y0 + y1) / 2, 0);
  };
  return mergeAll([
    ext(outline(), t * 0.42),
    ring(0, Rb, rb),
    ring(L, Rs, rs * 0.72),
    flange(wb - 0.025 * B, rb, ws - 0.025 * B, L - rs),
    flange(-wb + 0.025 * B, rb, -ws + 0.025 * B, L - rs),
  ]);
}

/** spark plug along +y from the gasket seat (0): thread, hex, ceramic insulator, terminal */
export function plugGeometries(B) {
  const k = B / 0.086; // drawn at a real 14 mm thread on an 86 mm bore, scaled with the bore
  const m = (v) => v * 0.001 * k;
  const thread = lathe([[0, -m(19)], [m(6.2), -m(19)], [m(7), -m(17)], [m(7), 0], [0, 0]], 16);
  const hex = new THREE.CylinderGeometry(m(9.5), m(9.5), m(9), 6).translate(0, m(4.5), 0);
  const ins = lathe([[0, m(9)], [m(6.5), m(9)], [m(6.5), m(15)], [m(5.4), m(17)], [m(5.4), m(19)], [m(5.8), m(20)], [m(5.4), m(21)], [m(5.4), m(23)], [m(5.8), m(24)], [m(5.4), m(25)], [m(5.4), m(36)], [m(3), m(37)], [0, m(37)]], 24);
  const term = new THREE.CylinderGeometry(m(2.4), m(2.4), m(8), 12).translate(0, m(40), 0);
  return {thread, hex, ins, term, length: m(44)};
}

/** a poly-V pulley of radius R and width w along z, n ribs */
export function polyVGeometry(R, w, n = 6) {
  const pts = [[R * 0.3, -w / 2], [R, -w / 2]];
  for (let i = 0; i < n; i++) {
    const z0 = -w / 2 + ((i + 0.5) / n) * w;
    pts.push([R * 0.94, z0], [R, z0 + (0.5 / n) * w]);
  }
  pts.push([R, w / 2], [R * 0.3, w / 2]);
  return lathe(pts.map(([r, z]) => [r, z]), 48).rotateX(Math.PI / 2);
}

/** hex bolt head with a washer, along +y from the seat (0) */
export function boltGeometry(B) {
  const k = B / 0.086;
  const head = new THREE.CylinderGeometry(0.0062 * k, 0.0062 * k, 0.0055 * k, 6).translate(0, 0.0045 * k, 0);
  const washer = new THREE.CylinderGeometry(0.0085 * k, 0.0085 * k, 0.0016 * k, 16).translate(0, 0.0008 * k, 0);
  return mergeAll([washer, head]);
}

/** multi-layer steel head gasket: the deck outline with a fire ring per bore */
export function gasketGeometry(B, half, z0, z1, zs, t) {
  const s = new THREE.Shape();
  s.moveTo(-half, z0);
  s.lineTo(half, z0);
  s.lineTo(half, z1);
  s.lineTo(-half, z1);
  s.closePath();
  for (const z of zs) {
    const h = new THREE.Path();
    h.absarc(0, z, 0.5 * B, 0, Math.PI * 2, true);
    s.holes.push(h);
  }
  for (const z of zs) for (const [x, dz] of [[-0.62, -0.5], [0.62, -0.5], [-0.62, 0.5], [0.62, 0.5]]) {
    if (Math.abs(x * B) > half - 0.06 * B) continue;
    const h = new THREE.Path();
    h.absarc(x * B, z + dz * B, 0.06 * B, 0, Math.PI * 2, true);
    s.holes.push(h);
  }
  // shape is drawn in (p, z); extrude along +y after rotating into the deck plane
  return new THREE.ExtrudeGeometry(s, {depth: t, bevelEnabled: false, curveSegments: 24}).rotateX(Math.PI / 2).translate(0, t, 0);
}

/** one roller-chain side plate: a waisted figure-of-eight between two pins at ±pitch/2 along x */
export function chainPlateGeometry(pitch, t) {
  const r = pitch * 0.42;
  const s = new THREE.Shape();
  s.absarc(-pitch / 2, 0, r, Math.PI / 2, (3 * Math.PI) / 2, false);
  s.quadraticCurveTo(0, -r * 0.6, pitch / 2, -r);
  s.absarc(pitch / 2, 0, r, -Math.PI / 2, Math.PI / 2, false);
  s.quadraticCurveTo(0, r * 0.6, -pitch / 2, r);
  return new THREE.ExtrudeGeometry(s, {depth: t, bevelEnabled: false, curveSegments: 10}).translate(0, 0, -t / 2);
}

/** a ribbed oil filter can along +y */
export function filterGeometry(B) {
  const pts = [[0, 0], [0.3 * B, 0], [0.3 * B, 0.04 * B]];
  for (let i = 0; i < 10; i++) {
    const y = 0.06 * B + i * 0.045 * B;
    pts.push([0.3 * B, y], [0.315 * B, y + 0.015 * B], [0.3 * B, y + 0.03 * B]);
  }
  pts.push([0.3 * B, 0.56 * B], [0.26 * B, 0.6 * B], [0, 0.61 * B]);
  return lathe(pts, 40);
}

/** merge non-indexed copies of several geometries into one (position and normal only) */
export function mergeAll(geos) {
  const parts = geos.map((g) => (g.index ? g.toNonIndexed() : g));
  const n = parts.reduce((a, g) => a + g.attributes.position.count, 0);
  const pos = new Float32Array(n * 3);
  const nor = new Float32Array(n * 3);
  let o = 0;
  for (const g of parts) {
    if (!g.attributes.normal) g.computeVertexNormals();
    pos.set(g.attributes.position.array, o * 3);
    nor.set(g.attributes.normal.array, o * 3);
    o += g.attributes.position.count;
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  return out;
}

/** many copies of one geometry as an instanced mesh: items are [position, direction (the geometry's +y)] */
export function instances(geo, mat, items) {
  const m = new THREE.InstancedMesh(geo, mat, Math.max(1, items.length));
  const q = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  const one = new THREE.Vector3(1, 1, 1);
  const M4 = new THREE.Matrix4();
  items.forEach(([p, d], i) => {
    q.setFromUnitVectors(up, d.clone().normalize());
    m.setMatrixAt(i, M4.compose(p, q, one));
  });
  m.count = items.length;
  m.castShadow = true;
  return m;
}

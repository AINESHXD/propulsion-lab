// A material library keyed by real alloys and coatings, shared by the JetLab and PistonLab 3D viewers. A part asks for
// an alloy by name (alloy('inconel718', {repeat: [u, v]})) and gets a physically based material with that metal's
// reflectance colour (F0 for metals), roughness, anisotropy, coating and surface detail; nothing is tuned per part.
//
// Surface detail is procedural and deterministic: canvas height fields (carbon twill, honeycomb, perforation, lathe
// turning marks, orange-peel paint, coating cracks, sand-cast grain) turned into tangent-space normal maps by central
// differences. No image files, no randomness: the same page renders the same pixels.
import * as THREE from 'three';

// ------------------------------------------------------------ deterministic noise and height fields
const hash = (x, y, s) => {
  let h = (x * 374761393 + y * 668265263 + s * 982451653) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
};
const vnoise = (x, y, s, period) => {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const fx = x - xi;
  const fy = y - yi;
  const u = fx * fx * (3 - 2 * fx);
  const v = fy * fy * (3 - 2 * fy);
  const w = (a, b) => hash(((a % period) + period) % period, ((b % period) + period) % period, s);
  return w(xi, yi) * (1 - u) * (1 - v) + w(xi + 1, yi) * u * (1 - v) + w(xi, yi + 1) * (1 - u) * v + w(xi + 1, yi + 1) * u * v;
};
const N = 256;
/** a tileable height field, h(x, y) in [0, 1] over a 0..1 square */
const field = (fn) => {
  const h = new Float32Array(N * N);
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) h[y * N + x] = fn(x / N, y / N, x, y);
  return h;
};
/** a tangent-space normal map from a height field, by central differences, wrapping at the edges */
const normalMap = (h, strength) => {
  const c = document.createElement('canvas');
  c.width = c.height = N;
  const g = c.getContext('2d');
  const img = g.createImageData(N, N);
  const at = (x, y) => h[((y + N) % N) * N + ((x + N) % N)];
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const dx = (at(x + 1, y) - at(x - 1, y)) * strength;
    const dy = (at(x, y + 1) - at(x, y - 1)) * strength;
    const l = Math.hypot(dx, dy, 1);
    const i = 4 * (y * N + x);
    img.data[i] = (0.5 - dx / (2 * l)) * 255;
    img.data[i + 1] = (0.5 - dy / (2 * l)) * 255;
    img.data[i + 2] = (0.5 + 0.5 / l) * 255;
    img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  return t;
};
/** a greyscale map (roughness, or a colour multiplier) from a height field */
const greyMap = (h, lo, hi, color = false) => {
  const c = document.createElement('canvas');
  c.width = c.height = N;
  const g = c.getContext('2d');
  const img = g.createImageData(N, N);
  for (let i = 0; i < N * N; i++) {
    const v = (lo + (hi - lo) * h[i]) * 255;
    img.data.set([v, v, v, 255], 4 * i);
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  if (color) t.colorSpace = THREE.SRGBColorSpace;
  return t;
};

const fields = {};
const F = (name, fn) => (fields[name] ||= field(fn));
// 2x2 twill: tows alternate over two and under two, stepping one each row; each tow is a rounded ridge
const twill = () => F('twill', (u, v) => {
  const n = 8;
  const cx = Math.floor(u * n);
  const cy = Math.floor(v * n);
  const over = (cx + cy) % 4 < 2;
  const fx = (u * n) % 1;
  const fy = (v * n) % 1;
  const ridge = over ? Math.sin(Math.PI * fy) : Math.sin(Math.PI * fx);
  return 0.5 + 0.45 * ridge * (over ? 1 : 0.85) + 0.05 * vnoise(u * 64, v * 64, 3, 64);
});
// hexagonal honeycomb cells: height is the distance to the nearest cell wall
const honeycomb = () => F('honey', (u, v) => {
  const n = 6;
  const x = u * n;
  const y = v * n;
  // axial coordinates of a pointy-top hex grid, then round to the nearest cell centre
  const q = (Math.sqrt(3) / 3) * x - y / 3;
  const r = (2 / 3) * y;
  let rx = Math.round(q);
  let rz = Math.round(r);
  const ry = Math.round(-q - r);
  const dx = Math.abs(rx - q);
  const dy = Math.abs(ry - (-q - r));
  const dz = Math.abs(rz - r);
  if (dx > dy && dx > dz) rx = -ry - rz;
  else if (dy <= dz) rz = -rx - ry;
  const d = Math.max(Math.abs(q - rx), Math.abs(r - rz), Math.abs(q - rx + r - rz));
  return Math.min(1, (0.5 - d) * 6);
});
// perforated skin: a staggered grid of round holes
const perforation = () => F('perf', (u, v) => {
  const n = 16;
  const row = Math.floor(v * n);
  const x = (u * n + (row % 2) * 0.5) % 1;
  const y = (v * n) % 1;
  const d = Math.hypot(x - 0.5, y - 0.5);
  return d < 0.17 ? 0 : 1;
});
// lathe turning: fine grooves across v (so they run round a lathe-made part), with a little chatter
const turned = () => F('turned', (u, v) => 0.5 + 0.35 * Math.sin(v * Math.PI * 2 * 96) + 0.15 * vnoise(u * 8, v * 256, 5, 8));
// orange peel: soft, low-amplitude blotches
const peel = () => F('peel', (u, v) => vnoise(u * 32, v * 32, 7, 32) * 0.7 + vnoise(u * 64, v * 64, 8, 64) * 0.3);
// a ceramic coating's hairline crack network: thin valleys along a cellular pattern
const cracks = () => F('cracks', (u, v) => {
  let best = 9;
  let second = 9;
  const n = 7;
  const cx = Math.floor(u * n);
  const cy = Math.floor(v * n);
  for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) {
    const gx = cx + i;
    const gy = cy + j;
    const px = (gx + hash(((gx % n) + n) % n, ((gy % n) + n) % n, 11)) / n;
    const py = (gy + hash(((gx % n) + n) % n, ((gy % n) + n) % n, 12)) / n;
    const d = Math.hypot(u - px, v - py);
    if (d < best) {
      second = best;
      best = d;
    } else if (d < second) second = d;
  }
  return Math.min(1, (second - best) * 60) * 0.8 + 0.2 * vnoise(u * 64, v * 64, 13, 64);
});
// sand-cast grain
const grain = () => F('grain', (u, v) => 0.55 * vnoise(u * 48, v * 48, 1, 48) + 0.45 * vnoise(u * 128, v * 128, 2, 128));
// a weave for ceramic-matrix composite: plain weave, coarser and flatter than the carbon twill
const plain = () => F('plain', (u, v) => {
  const n = 10;
  const over = (Math.floor(u * n) + Math.floor(v * n)) % 2 === 0;
  return 0.5 + 0.4 * (over ? Math.sin(Math.PI * ((v * n) % 1)) : Math.sin(Math.PI * ((u * n) % 1)));
});

// film cooling on a turbine airfoil, on the blade loft's UVs (u round the section, trailing edge at 0 and 1, leading
// edge at 0.5; v from hub to tip): a showerhead of three rows at the leading edge, two gill rows on each side, and
// trailing-edge slots
const film = () => F('film', (u, v) => {
  const rows = [[0.47, 0], [0.5, 0.5], [0.53, 0], [0.38, 0.25], [0.62, 0.75], [0.3, 0.5], [0.7, 0]];
  let h = 1;
  for (const [u0, off] of rows) {
    const vv = (v * 16 + off) % 1;
    const d = Math.hypot((u - u0) * 60, (vv - 0.5) * 2.2);
    if (d < 0.5) h = Math.min(h, d / 0.5);
  }
  // trailing-edge slots: short spanwise cuts either side of u = 0 / 1
  const te = Math.min(u, 1 - u);
  if (te < 0.02 && (v * 22) % 1 < 0.6) h = Math.min(h, 0.15);
  return h;
});
// effusion cooling on a combustor liner: a dense staggered array of small angled holes
const effusion = () => F('eff', (u, v) => {
  const n = 24;
  const row = Math.floor(v * n);
  const x = (u * n + (row % 2) * 0.5) % 1;
  const y = (v * n) % 1;
  const d = Math.hypot((x - 0.5) * 1.0, (y - 0.5) * 2.2);
  return d < 0.16 ? d / 0.16 : 1;
});
// regenerative cooling channels: parallel ribs and grooves
const channels = () => F('chan', (u, v) => 0.5 + 0.5 * Math.sign(Math.sin(u * Math.PI * 2 * 12)) * 0.9);

const maps = {};
const M = (key, fn) => (maps[key] ||= fn());

// ------------------------------------------------------------ the library
// base: colour (sRGB) or metal F0, metalness, roughness, plus extensions; detail: which normal map and its strength
const LIB = {
  // Ti-6Al-4V: fan blades, early compressor, casings. Cool grey with a faint warm cast, polished along the span.
  ti64: {color: '#b4b6b8', metalness: 1, roughness: 0.3, anisotropy: 0.45, detail: ['turned', 0.25]},
  // Inconel 718 / Waspaloy: discs, shafts, hot casings. Darker, warmer; turned concentric marks; a hint of heat blue.
  inconel718: {color: '#a39b91', metalness: 1, roughness: 0.38, anisotropy: 0.6, iridescence: 0.18, iridescenceIOR: 1.6, iridescenceThicknessRange: [180, 340], detail: ['turned', 0.35]},
  // single-crystal nickel with a thermal barrier coating: HP turbine blades and vanes. Pale cream ceramic, rough,
  // hairline cracked.
  cmsxTbc: {color: '#d7cfbf', metalness: 0, roughness: 0.72, detail: ['cracks', 1.4]},
  // the same, on airfoils, with film cooling holes and trailing-edge slots
  cmsxFilm: {color: '#d7cfbf', metalness: 0, roughness: 0.72, detail: ['film', 2.5], colorDetail: 'film'},
  // a combustor liner's effusion-cooled wall
  tbcEffusion: {color: '#d4ccbb', metalness: 0, roughness: 0.75, detail: ['eff', 2.0], colorDetail: 'eff'},
  // a regeneratively cooled panel seen in section: copper-alloy ribs over the coolant channels
  coolPanel: {color: '#b9805a', metalness: 1, roughness: 0.4, detail: ['chan', 2.5], colorDetail: 'chan'},
  // ceramic-matrix composite: shrouds and liners. Matte dark grey, woven fibre.
  cmc: {color: '#4a4c4f', metalness: 0, roughness: 0.78, sheen: 0.3, sheenColor: '#6a6e74', detail: ['plain', 1.6]},
  // steels: shafts, gears, bearings, fasteners. Neutral; bearings polished.
  steel: {color: '#c3c6ca', metalness: 1, roughness: 0.28, anisotropy: 0.3, detail: ['turned', 0.25]},
  bearing: {color: '#d8dadd', metalness: 1, roughness: 0.12},
  stainlessHot: {color: '#a8a39c', metalness: 1, roughness: 0.38, iridescence: 0.45, iridescenceIOR: 1.6, iridescenceThicknessRange: [160, 360]},
  // aluminium: sand castings (gearbox, intake, blocks, heads) and machined faces
  alCast: {color: '#a9adb1', metalness: 0.75, roughness: 0.6, detail: ['grain', 2.2], roughDetail: 'grain'},
  alMachined: {color: '#d4d7da', metalness: 1, roughness: 0.25, anisotropy: 0.5, detail: ['turned', 0.25]},
  // cast iron: older blocks, exhaust manifolds. Dark and slightly rough.
  castIron: {color: '#5d5f62', metalness: 0.8, roughness: 0.62, detail: ['grain', 2.6], roughDetail: 'grain'},
  // carbon-fibre composite: fan blades, fan case, nacelle parts. Twill weave under a clear coat.
  cfrp: {color: '#1f2124', metalness: 0.15, roughness: 0.42, clearcoat: 1, clearcoatRoughness: 0.12, sheen: 0.25, sheenColor: '#55595f', detail: ['twill', 2.0]},
  // honeycomb abradable liner: fan case over the blade tips, compressor and turbine seals
  honeycomb: {color: '#8d8a84', metalness: 0.4, roughness: 0.7, detail: ['honey', 3.0]},
  // acoustic liner: perforated skin over honeycomb, in the inlet and the bypass duct
  acoustic: {color: '#6f7377', metalness: 0.5, roughness: 0.55, detail: ['perf', 2.5], colorDetail: 'perf'},
  // painted metal: spinner, nacelle, covers. Satin paint with orange peel under a clear coat.
  paintWhite: {color: '#d4d7da', metalness: 0, roughness: 0.38, clearcoat: 0.7, clearcoatRoughness: 0.22, detail: ['peel', 0.5]},
  paintGrey: {color: '#5b6067', metalness: 0, roughness: 0.4, clearcoat: 0.6, clearcoatRoughness: 0.25, detail: ['peel', 0.5]},
  paintBlack: {color: '#1d1f22', metalness: 0, roughness: 0.32, clearcoat: 1, clearcoatRoughness: 0.12, detail: ['peel', 0.4]},
  // copper alloys: fittings, bushings, cages
  bronze: {color: '#c39a62', metalness: 1, roughness: 0.4},
  brass: {color: '#d2b276', metalness: 1, roughness: 0.32},
  // elastomers and polymers: hoses, seals, gaskets
  rubber: {color: '#1a1b1d', metalness: 0, roughness: 0.78, sheen: 0.2, sheenColor: '#40434a'},
  // ceramic monolith: catalytic converter substrate
  cordierite: {color: '#ddd5c4', metalness: 0, roughness: 0.85, detail: ['honey', 2.0]},
  // glass and polycarbonate: sight glasses, sensor windows
  glass: {color: '#ffffff', metalness: 0, roughness: 0.05, transmission: 1, ior: 1.5, thickness: 0.004},
};

const DETAIL = {twill, honey: honeycomb, perf: perforation, turned, peel, cracks, grain, plain, film, eff: effusion, chan: channels};

/** a new material of the named alloy; repeat: how many times the detail tiles across the part's UVs */
export function alloy(name, {repeat = [8, 8], side} = {}) {
  const L = LIB[name];
  if (!L) throw new Error(`no alloy ${name}`);
  const {detail, roughDetail, colorDetail, ...base} = L;
  const m = new THREE.MeshPhysicalMaterial({envMapIntensity: 1, ...base});
  if (side != null) m.side = side;
  const rep = (t) => {
    const c = t.clone();
    c.repeat.set(repeat[0], repeat[1]);
    c.needsUpdate = true;
    return c;
  };
  if (detail) {
    const [key, strength] = detail;
    m.normalMap = rep(M(`n-${key}-${strength}`, () => normalMap(DETAIL[key](), strength)));
    m.normalScale.set(1, 1);
  }
  if (roughDetail) m.roughnessMap = rep(M(`r-${roughDetail}`, () => greyMap(DETAIL[roughDetail](), 0.75, 1.15)));
  if (colorDetail) m.map = rep(M(`c-${colorDetail}`, () => greyMap(DETAIL[colorDetail](), 0.25, 1, true)));
  m.userData.alloy = name;
  return m;
}

export const ALLOYS = Object.keys(LIB);

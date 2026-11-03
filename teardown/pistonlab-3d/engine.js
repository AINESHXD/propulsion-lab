// The engine built from code, sized from one makeEngine() description, as a technical model in layers: block and
// crankcase, the rotating assembly, heads, the valvetrain (overhead cams with bucket followers, or a block cam with
// lifters, pushrods and rockers), the cam drive, lubrication, intake, exhaust with a turbo when fitted, ignition and
// fuel, the accessory belt, and the charge itself. update(th, opts) poses every moving part for crank angle th.
//
// One source for the motion: every cam lobe is generated from the same lift curve that lifts its valve, so the lobe,
// the follower, the valve and the readout cannot disagree. The cams turn at half crank speed; the drive sprockets and
// pulleys turn at the ratio of their drawn radii, so the chain and belt never slip.
import * as THREE from 'three';
import {alloy} from '../shared/alloys.js';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
import {blackbody, boltGeometry, roundedBox, bossGeometry, chainPlateGeometry, filterGeometry, gasketGeometry, glowIntensity, instances, makeMaterials, pistonGeometry, plugGeometries, polyVGeometry, ringGeometries, rodGeometry} from './detail.js';
import {chargeOf, mod} from './kin.js';

const D2R = Math.PI / 180;
const V3 = THREE.Vector3;
export const ACCENT = '#e8923e';
const CHARGE = [new THREE.Color('#4f9be0'), new THREE.Color('#2f6fb8'), new THREE.Color('#ff8a1f'), new THREE.Color('#8d877c')];

export const LAYERS = [
  {id: 'block', name: 'Block and crankcase'},
  {id: 'rotating', name: 'Crank, rods and pistons'},
  {id: 'head', name: 'Heads and covers'},
  {id: 'valvetrain', name: 'Valvetrain'},
  {id: 'timing', name: 'Cam drive'},
  {id: 'lube', name: 'Lubrication'},
  {id: 'intake', name: 'Intake'},
  {id: 'exhaust', name: 'Exhaust'},
  {id: 'ignition', name: 'Ignition and fuel'},
  {id: 'accessory', name: 'Accessory drive'},
  {id: 'charge', name: 'Cylinder charge'},
];

const std = (color, metalness, roughness, extra = {}) => new THREE.MeshStandardMaterial({color, metalness, roughness, envMapIntensity: 0.7, ...extra});
const lathe = (pts, seg = 36) => new THREE.LatheGeometry(pts.map(([x, y]) => new THREE.Vector2(x, y)), seg);
const tube = (pts, r, closed = false, seg = 64) => new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, closed, 'centripetal'), seg, r, 12, closed);
// a pipe with a domed cap on each end, so an end never shows as an open, paper-thin ring (exhaust headers, collectors)
const ctube = (pts, r, seg = 64) => {
  const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
  const geos = [new THREE.TubeGeometry(curve, seg, r, 12, false)];
  for (const [t, s] of [[0, -1], [1, 1]]) {
    const cap = new THREE.SphereGeometry(r, 12, 6, 0, Math.PI * 2, 0, Math.PI / 2);
    cap.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new V3(0, 1, 0), curve.getTangentAt(t).multiplyScalar(s)));
    const at = curve.getPointAt(t);
    cap.translate(at.x, at.y, at.z);
    geos.push(cap);
  }
  return mergeGeometries(geos);
};
/** a cylinder of unit length along +y from 0 to 1 */
const rod01 = (r, seg = 16) => new THREE.CylinderGeometry(r, r, 1, seg).translate(0, 0.5, 0);
const along = (mesh, a, b) => {
  const d = new V3().subVectors(b, a);
  mesh.position.copy(a);
  mesh.scale.set(1, d.length(), 1);
  mesh.quaternion.setFromUnitVectors(new V3(0, 1, 0), d.normalize());
};
/** a sprocket or toothed pulley: n teeth on radius R */
const gearGeo = (R, n, t, tooth = 0.12) => {
  const s = new THREE.Shape();
  const k = 4 * n;
  for (let i = 0; i <= k; i++) {
    const a = (i / k) * Math.PI * 2;
    const r = i % 4 < 2 ? R : R * (1 - tooth);
    const x = r * Math.sin(a);
    const y = r * Math.cos(a);
    i ? s.lineTo(x, y) : s.moveTo(x, y);
  }
  const h = new THREE.Path();
  h.absarc(0, 0, R * 0.25, 0, Math.PI * 2, true);
  s.holes.push(h);
  return new THREE.ExtrudeGeometry(s, {depth: t, bevelEnabled: false, curveSegments: 4}).translate(0, 0, -t / 2);
};
/** the convex hull (counter-clockwise, seen from +z) round a set of circles, as a closed polyline */
const hull = (circles) => {
  const pts = [];
  for (const c of circles) for (let i = 0; i < 64; i++) {
    const a = (i / 64) * Math.PI * 2;
    pts.push([c.x + c.r * Math.cos(a), c.y + c.r * Math.sin(a)]);
  }
  pts.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo = [];
  for (const p of pts) {
    while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop();
    lo.push(p);
  }
  const up = [];
  for (const p of pts.slice().reverse()) {
    while (up.length >= 2 && cross(up[up.length - 2], up[up.length - 1], p) <= 0) up.pop();
    up.push(p);
  }
  return lo.slice(0, -1).concat(up.slice(0, -1));
};
/** arc-length table of a closed polyline */
const pathTable = (poly) => {
  const cum = [0];
  for (let i = 1; i <= poly.length; i++) {
    const a = poly[i - 1];
    const b = poly[i % poly.length];
    cum.push(cum[i - 1] + Math.hypot(b[0] - a[0], b[1] - a[1]));
  }
  const L = cum[cum.length - 1];
  const at = (s) => {
    s = mod(s, L);
    let i = 1;
    while (cum[i] < s) i++;
    const a = poly[i - 1];
    const b = poly[i % poly.length];
    const k = (s - cum[i - 1]) / (cum[i] - cum[i - 1] || 1);
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, Math.atan2(b[1] - a[1], b[0] - a[0])];
  };
  return {L, at};
};

export function buildEngine(E) {
  const B = E.bore;
  const hw = E.hw;
  const root = new THREE.Group();
  const CLIP = new THREE.Plane(new V3(0, 0, -1), 0);
  const movers = [];
  const shells = [];
  const shellMeshes = [];

  // ------------------------------------------------------------ layers, banks, picking
  const layer = {};
  for (const L of LAYERS) {
    layer[L.id] = new THREE.Group();
    layer[L.id].userData.layer = L.id;
    root.add(layer[L.id]);
  }
  const explodable = []; // {g, v: world offset at full explode}
  const ex = (g, v) => (explodable.push({g, v}), g);
  const sideOf = (b, p) => {
    // intake on the side facing the valley (V), the top (flat) or +p (inline)
    if (Math.abs(b[0]) > 0.9) return Math.sign(p[1]) || 1;
    if (Math.abs(b[0]) > 0.05) return -Math.sign(p[0] * b[0]) || 1;
    return 1;
  };
  const banks = [...new Set(E.cyl.map((c) => c.bank))].map((id) => {
    const cs = E.cyl.filter((c) => c.bank === id);
    const c = cs[0];
    const sIn = sideOf(c.b, c.p);
    return {id, cs, axis: c.axis, b: c.b, p: c.p, sIn, sEx: -sIn, z0: Math.min(...cs.map((x) => x.z)), z1: Math.max(...cs.map((x) => x.z))};
  });
  const multi = banks.length > 1;
  const W = (bk, pl, bl, z = 0) => new V3(pl * bk.p[0] + bl * bk.b[0], pl * bk.p[1] + bl * bk.b[1], z);
  const bankGroup = (lay, bk, dist) => {
    const g = new THREE.Group();
    g.rotation.z = -bk.axis * D2R;
    layer[lay].add(g);
    return ex(g, new V3(bk.b[0], bk.b[1], 0).multiplyScalar(dist));
  };
  const worldGroup = (lay, v) => {
    const g = new THREE.Group();
    layer[lay].add(g);
    return ex(g, v);
  };
  const part = (obj, id, meta = {}) => {
    obj.userData.pick = {id, meta};
    return obj;
  };
  const shell = (m) => {
    m.userData.shell = true;
    shells.push(m);
    return m;
  };

  // ------------------------------------------------------------ materials
  const M = makeMaterials(hw);
  const glassMat = () => new THREE.MeshStandardMaterial({color: '#9fc3e6', metalness: 0, roughness: 0.15, transparent: true, opacity: 0.12, depthWrite: false, side: THREE.DoubleSide});
  const shellMat = (color) => {
    const m = M.castShell(color);
    Object.assign(m, {transparent: true, opacity: 0.1, depthWrite: false, side: THREE.DoubleSide});
    return shell(m);
  };
  const boltGeo = boltGeometry(B);
  /** a set of hex bolts in a group's own frame: items are [position, direction] */
  const bolts = (g, items) => g.add(instances(boltGeo, M.bolt, items));
  const edgeMat = new THREE.LineBasicMaterial({color: '#7d8691', transparent: true, opacity: 0.45});
  const boxWithEdges = (g, geo, mat, pos, id, meta) => {
    const m = part(new THREE.Mesh(geo, mat), id, meta);
    m.position.copy(pos);
    m.renderOrder = 3;
    g.add(m);
    const e = new THREE.LineSegments(new THREE.EdgesGeometry(geo, 20), edgeMat);
    e.position.copy(pos);
    g.add(e);
    return m;
  };
  const bevBox = (w, h, d) => roundedBox(w, h, d, 0.18 * Math.min(w, h, d));
  const plastic = std('#24272b', 0.05, 0.42);
  const wire = std('#121416', 0.0, 0.55);
  const braid = std('#9aa0a7', 0.8, 0.5);
  const clampGeo = new THREE.TorusGeometry(1, 0.14, 6, 24);
  const screwGeo = roundedBox(0.5, 0.36, 0.5, 0.08);
  /** a hose on a path, with a worm-drive clamp near each end */
  const hose = (g, pts, r, id, meta = {}, mat = M.rubber, clamps = true) => {
    const m = part(new THREE.Mesh(tube(pts, r, false, Math.max(24, 14 * pts.length)), mat), id, meta);
    g.add(m);
    if (clamps) for (const [a, b] of [[pts[0], pts[1]], [pts[pts.length - 1], pts[pts.length - 2]]]) {
      const d = new V3().subVectors(b, a).normalize();
      const at = a.clone().addScaledVector(d, Math.min(0.1 * B, a.distanceTo(b) * 0.3));
      const q = new THREE.Quaternion().setFromUnitVectors(new V3(0, 0, 1), d);
      const c = part(new THREE.Mesh(clampGeo, M.steel), id, meta);
      c.scale.setScalar(r * 1.1);
      c.position.copy(at);
      c.quaternion.copy(q);
      const sc = part(new THREE.Mesh(screwGeo, M.steel), id, meta);
      sc.scale.setScalar(r);
      sc.position.copy(at).add(new V3(0, r * 1.25, 0).applyQuaternion(q));
      sc.quaternion.copy(q);
      g.add(c, sc);
    }
    return m;
  };
  const hexGeo = new THREE.CylinderGeometry(0.06, 0.06, 0.05, 6).translate(0, 0.025, 0);
  const senderGeo = new THREE.CylinderGeometry(0.042, 0.05, 0.13, 16).translate(0, 0.115, 0);
  const plugBodyGeo = roundedBox(0.13, 0.085, 0.1, 0.018).translate(0.035, 0.22, 0);
  const latchGeo = roundedBox(0.04, 0.03, 0.06, 0.008).translate(0.035, 0.27, 0);
  /** a screw-in sensor: hex, body, a moulded connector with its latch, and a lead curling away to the loom */
  const sensor = (g, at, dir, id, meta = {}, size = 1) => {
    const k = size * B;
    const s = part(new THREE.Group(), id, meta);
    const hx = new THREE.Mesh(hexGeo, M.bolt);
    const body = new THREE.Mesh(senderGeo, plastic);
    const con = new THREE.Mesh(plugBodyGeo, plastic);
    const latch = new THREE.Mesh(latchGeo, M.black);
    const lead = new THREE.Mesh(tube([new V3(0.1, 0.22, 0), new V3(0.22, 0.24, 0.03), new V3(0.34, 0.16, 0.16), new V3(0.42, 0.05, 0.34)], 0.017, false, 20), wire);
    s.add(hx, body, con, latch, lead);
    s.scale.setScalar(k);
    s.position.copy(at);
    s.quaternion.setFromUnitVectors(new V3(0, 1, 0), dir.clone().normalize());
    g.add(s);
    return s;
  };
  /** n bolts evenly from a to b, all pointing along dir */
  const boltRow = (g, a, b, n, dir) => {
    const items = [];
    for (let i = 0; i < n; i++) items.push([a.clone().lerp(b, n === 1 ? 0.5 : i / (n - 1)), dir]);
    bolts(g, items);
  };
  // oil that visibly moves: a dash texture whose offset follows the crank
  const flowTex = (() => {
    const c = document.createElement('canvas');
    c.width = 64;
    c.height = 4;
    const g = c.getContext('2d');
    g.fillStyle = '#8a5b14';
    g.fillRect(0, 0, 64, 4);
    g.fillStyle = '#ffc861';
    g.fillRect(0, 0, 24, 4);
    const t = new THREE.CanvasTexture(c);
    t.wrapS = THREE.RepeatWrapping;
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  })();
  const flowMat = new THREE.MeshStandardMaterial({map: flowTex, emissive: '#7a4a08', emissiveIntensity: 0.15, roughness: 0.4});
  const oilLine = (g, pts, r, id, meta) => {
    const geo = tube(pts, r);
    // one dash per two bores of line, whatever its length
    const len = new THREE.CatmullRomCurve3(pts).getLength();
    const uv = geo.attributes.uv;
    for (let i = 0; i < uv.count; i++) uv.setX(i, uv.getX(i) * (len / (2 * B)));
    const m = part(new THREE.Mesh(geo, flowMat), id, meta);
    g.add(m);
    return m;
  };

  // ------------------------------------------------------------ dimensions everything hangs off
  const zs = E.cyl.map((c) => c.z);
  const zFront = Math.max(...zs) + 0.75 * B;
  const zRear = Math.min(...zs) - 0.75 * B;
  const zMid = (zFront + zRear) / 2;
  const mainR = 0.27 * B;
  const caseR = E.r + 0.9 * B; // crankcase half-width: clears the webs and counterweights
  const bBot = E.sBDC + E.crownH - 0.77 * B; // bottom of the cylinder barrels, along each bank
  const Ls = 0.62 * B; // valve length, head face to tip
  const ohv = hw.valvetrain === 'ohv';
  const sohc = hw.valvetrain === 'sohc';
  const gam = ohv || sohc ? 0 : 21 * D2R; // valve splay from the bore axis
  const bucketH = 0.1 * B;
  const camBase = 0.17 * B;
  const nIn = Math.max(1, Math.min(3, E.vg.intake_valves_per_cylinder));
  const nEx = Math.max(1, Math.min(3, E.vg.exhaust_valves_per_cylinder));
  const dIn = E.vg.intake_valve_diameter_ratio * B;
  const dEx = E.vg.exhaust_valve_diameter_ratio * B;
  const liftMax = {in: E.vg.max_lift_ratio * dIn, ex: E.vg.max_lift_ratio * dEx};
  const rr = hw.rocker_ratio;
  // seats: splayed pairs across the bore (DOHC), or a line along the crank under one cam (SOHC, OHV)
  const seats = (kind, side) => {
    const n = kind === 'in' ? nIn : nEx;
    const d = kind === 'in' ? dIn : dEx;
    if (ohv || sohc) return [{p: 0, z: (kind === 'in' ? 1 : -1) * (0.49 * B - d / 2)}];
    const out = [];
    const spread = n === 1 ? 0 : Math.min(0.24 * B, (0.94 * B - d) / 2);
    for (let k = 0; k < n; k++) {
      const zz = n === 1 ? 0 : -spread + (2 * spread * k) / (n - 1);
      const lim = 0.47 * B - d / 2;
      out.push({p: side * Math.min(0.22 * B, Math.sqrt(Math.max(0, lim * lim - zz * zz))), z: zz});
    }
    return out;
  };
  const camCenter = (bk, kind) => {
    const side = kind === 'in' ? bk.sIn : bk.sEx;
    const s0 = seats(kind, side)[0];
    const u = [side * Math.sin(gam), Math.cos(gam)];
    const d = Ls + bucketH + camBase;
    return [s0.p + u[0] * d, E.deck + u[1] * d];
  };
  const camTopB = ohv ? E.deck + Ls + 0.25 * B : camCenter(banks[0], 'in')[1] + camBase + liftMax.in + 0.14 * B;
  const headTop = E.deck + 0.6 * B;
  const headHalf = ohv ? 0.78 * B : sohc ? 0.72 * B : Math.abs(camCenter(banks[0], 'in')[0]) + camBase + 0.32 * B;

  // ------------------------------------------------------------ rotating assembly
  const crank = part(new THREE.Group(), 'crank');
  layer.rotating.add(crank);
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(mainR, mainR, zFront - zRear, 36), M.steel);
  shaft.rotation.x = Math.PI / 2;
  shaft.position.z = zMid;
  crank.add(shaft);
  const nose = new THREE.Mesh(new THREE.CylinderGeometry(0.2 * B, 0.2 * B, 0.9 * B, 24), M.steel);
  nose.rotation.x = Math.PI / 2;
  nose.position.z = zFront + 0.45 * B;
  crank.add(nose);
  const throws = [];
  for (const c of E.cyl) {
    const t = throws.find((x) => Math.abs(mod(x.pin - c.pin + 180, 360) - 180) < 0.5 && Math.abs(x.z - c.z) < 0.4 * B);
    if (t) {
      t.cyl.push(c);
      t.z = (t.z * (t.cyl.length - 1) + c.z) / t.cyl.length;
    } else throws.push({pin: c.pin, z: c.z, cyl: [c]});
  }
  const rodW = 0.2 * B;
  const pinR = 0.24 * B;
  const webT = 0.1 * B;
  const webShape = new THREE.Shape();
  webShape.absarc(0, E.r, pinR * 1.35, 0, Math.PI, false);
  webShape.absarc(0, -0.12 * B, 0.5 * B, Math.PI * 1.08, Math.PI * 1.92, false);
  webShape.closePath();
  const webGeo = new THREE.ExtrudeGeometry(webShape, {depth: webT, bevelEnabled: true, bevelSize: 0.008 * B, bevelThickness: 0.008 * B, bevelSegments: 2, curveSegments: 24});
  webGeo.translate(0, 0, -webT / 2);
  for (const t of throws) {
    const g = new THREE.Group();
    g.position.z = t.z;
    g.rotation.z = -t.pin * D2R;
    const len = (rodW + 0.04 * B) * t.cyl.length;
    t.len = len;
    const pin = new THREE.Mesh(new THREE.CylinderGeometry(pinR, pinR, len, 28), M.steel);
    pin.rotation.x = Math.PI / 2;
    pin.position.y = E.r;
    g.add(pin);
    for (const s of [-1, 1]) {
      const w = new THREE.Mesh(webGeo, M.forged);
      w.position.z = s * (len / 2 + webT / 2);
      w.castShadow = true;
      g.add(w);
    }
    crank.add(g);
  }
  const fly = new THREE.Group();
  const flyDisc = new THREE.Mesh(new THREE.CylinderGeometry(0.95 * B, 0.95 * B, 0.14 * B, 64), M.forged);
  flyDisc.rotation.x = Math.PI / 2;
  const ring = new THREE.Mesh(gearGeo(1.0 * B, 60, 0.1 * B, 0.05), M.steel);
  fly.add(flyDisc, ring);
  fly.position.z = zRear - 0.07 * B;
  part(fly, 'flywheel');
  crank.add(fly);
  const mark = new THREE.Mesh(bevBox(0.08 * B, 0.3 * B, 0.02 * B), std(ACCENT, 0.2, 0.6));
  mark.position.set(0, 0.75 * B, zRear - 0.15 * B);
  crank.add(mark);
  movers.push((th) => (crank.rotation.z = -th * D2R));

  // balance shafts (data from the gallery): one primary shaft at crank speed turning the other way, or a pair at
  // twice crank speed for the second order
  if (hw.balance_shafts > 0) {
    const n = hw.balance_shafts;
    for (let k = 0; k < n; k++) {
      const g = part(new THREE.Group(), 'balance', {k});
      const x = (n === 1 ? -1 : k ? 1 : -1) * (E.r + 0.55 * B);
      g.position.set(x, -0.25 * B, 0);
      const sh = new THREE.Mesh(new THREE.CylinderGeometry(0.12 * B, 0.12 * B, zFront - zRear, 20), M.steel);
      sh.rotation.x = Math.PI / 2;
      sh.position.z = zMid;
      g.add(sh);
      const lobe = new THREE.Mesh(new THREE.CylinderGeometry(0.34 * B, 0.34 * B, 0.3 * B, 24, 1, false, -Math.PI / 2, Math.PI), M.forged);
      lobe.rotation.x = Math.PI / 2;
      for (const zz of [zFront - 0.4 * B, zRear + 0.4 * B]) {
        const l = lobe.clone();
        l.position.z = zz;
        g.add(l);
      }
      layer.rotating.add(g);
      const order = n === 1 ? 1 : 2;
      const dir = n === 1 ? 1 : k ? 1 : -1;
      movers.push((th) => (g.rotation.z = dir * order * th * D2R));
    }
  }

  // pistons, rods, liners, charge
  const pistonGeo = pistonGeometry(B, hw.diesel);
  // circlips that hold the wrist pin in its bosses
  const clipGeo = new THREE.TorusGeometry(0.1 * B, 0.012 * B, 6, 24);
  const pistonMat = M.alu.clone();
  pistonMat.userData.wearRole = 'carbon';
  pistonMat.side = THREE.DoubleSide;
  const ringGeos = ringGeometries(B);
  const bossGeos = bossGeometry(B, E.crownH);
  const wristGeo = new THREE.CylinderGeometry(0.11 * B, 0.11 * B, 0.9 * B, 16).rotateX(Math.PI / 2);
  const rodGeo = rodGeometry(B, E.L, rodW * 0.9);
  const rodBolts = [[-0.27 * B, -0.3 * B], [0.27 * B, -0.3 * B]].map(([x, y]) => [new V3(x, y, 0), new V3(0, -1, 0)]);
  const linerLen = E.deck - bBot;
  const linerGeo = new THREE.CylinderGeometry(0.53 * B, 0.53 * B, linerLen, 48, 1, true);
  const rimGeo = new THREE.TorusGeometry(0.53 * B, 0.012 * B, 8, 64).rotateX(Math.PI / 2);
  const chargeGeo = new THREE.CylinderGeometry(0.485 * B, 0.485 * B, 1, 40).translate(0, 0.5, 0);
  const C = [];
  const portSprays = [];
  for (const c of E.cyl) {
    const rot = -c.axis * D2R;
    const at = (d) => [d * c.b[0], d * c.b[1]];
    const glass = glassMat();
    shells.push(glass);
    const liner = part(new THREE.Mesh(linerGeo, glass), 'liner', {cyl: c.n});
    liner.position.set(...at(E.deck - linerLen / 2), c.z);
    liner.rotation.z = rot;
    liner.renderOrder = 2;
    layer.block.add(liner);
    const rimMat = std('#6c737c', 0.4, 0.5);
    const rim = new THREE.Mesh(rimGeo, rimMat);
    rim.position.set(...at(E.deck), c.z);
    rim.rotation.z = rot;
    layer.block.add(rim);
    const piston = part(new THREE.Group(), 'piston', {cyl: c.n});
    const pm = new THREE.Mesh(pistonGeo, pistonMat);
    pm.castShadow = true;
    const wp = new THREE.Mesh(wristGeo, M.pin);
    for (const zz of [-0.43 * B, 0.43 * B]) {
      const clip = new THREE.Mesh(clipGeo, M.steel);
      clip.position.set(0, -E.crownH, zz);
      piston.add(clip);
    }
    wp.position.y = -E.crownH;
    piston.add(pm, wp, ...ringGeos.map((g, i) => new THREE.Mesh(g, i === 2 ? M.forged : M.steel)), ...bossGeos.map((g) => new THREE.Mesh(g, pistonMat)));
    piston.rotation.z = rot;
    layer.rotating.add(piston);
    const rod = part(new THREE.Group(), 'rod', {cyl: c.n});
    const shank = new THREE.Mesh(rodGeo, M.forged);
    shank.castShadow = true;
    const brg = new THREE.Mesh(new THREE.CylinderGeometry(0.34 * B, 0.34 * B, rodW * 0.86, 28, 1, true).rotateX(Math.PI / 2), M.bronze);
    brg.material.side = THREE.DoubleSide;
    rod.add(shank, brg);
    bolts(rod, rodBolts);
    layer.rotating.add(rod);
    const cm = new THREE.MeshStandardMaterial({color: CHARGE[0], transparent: true, opacity: 0.5, roughness: 0.9, metalness: 0, depthWrite: false, emissive: '#000000', emissiveIntensity: 0});
    const charge = part(new THREE.Mesh(chargeGeo, cm), 'charge', {cyl: c.n});
    charge.rotation.z = rot;
    charge.renderOrder = 1;
    layer.charge.add(charge);
    C.push({c, piston, rod, charge, cm, rimMat, glass, plugMat: null});
  }

  // ------------------------------------------------------------ block and crankcase
  {
    // the block's alloy, from the gallery: grey cast iron or a sand-cast aluminium alloy
    const cm = hw.block === 'iron' ? shell(Object.assign(alloy('castIron', {repeat: [6, 6]}), {transparent: true, opacity: 0.1, depthWrite: false, side: THREE.DoubleSide})) : shellMat('#a4a7ab');
    for (const bk of banks) {
      const g = new THREE.Group();
      g.rotation.z = -bk.axis * D2R;
      layer.block.add(g);
      const bh = E.deck - bBot;
      const bl = bk.z1 - bk.z0 + 1.24 * B;
      const by = (E.deck + bBot) / 2;
      const bz = (bk.z0 + bk.z1) / 2;
      boxWithEdges(g, roundedBox(1.12 * B, bh, bl, 0.07 * B), cm, new V3(0, by, bz), 'block');
      // the water jacket round each bore stands proud of the casting, one bulge per cylinder
      const bulge = new THREE.CylinderGeometry(0.6 * B, 0.6 * B, bh - 0.22 * B, 48);
      for (const c of bk.cs) {
        const m = part(new THREE.Mesh(bulge, cm), 'block');
        m.position.set(0, by - 0.02 * B, c.z);
        g.add(m);
      }
      // a machined deck rail and a stiffening rib down each side
      for (const sx of [-1, 1]) {
        const rail = part(new THREE.Mesh(roundedBox(0.12 * B, 0.12 * B, bl, 0.03 * B), cm), 'block');
        rail.position.set(sx * 0.6 * B, E.deck - 0.07 * B, bz);
        const rib = part(new THREE.Mesh(roundedBox(0.08 * B, 0.07 * B, bl, 0.025 * B), cm), 'block');
        rib.position.set(sx * 0.6 * B, bBot + 0.12 * B, bz);
        g.add(rail, rib);
      }
      // knock sensors bolted to the intake-side wall
      const kz = bk.cs.length > 2 ? [bk.cs[1].z, bk.cs[bk.cs.length - 2].z] : [bz];
      for (const z of kz) sensor(g, new V3(bk.sIn * 0.6 * B, by + 0.15 * B, z + 0.59 * B), new V3(bk.sIn, 0, 0), 'knock-sensor', {bank: bk.id}, 0.9);
      // pressed-in core plugs between the bores, both walls, where the casting sand came out
      const zc = bk.cs.length > 1 ? bk.cs.slice(1).map((c, i) => (c.z + bk.cs[i].z) / 2) : [bk.cs[0].z - 0.35 * B, bk.cs[0].z + 0.35 * B];
      const plugGeo = new THREE.CylinderGeometry(0.13 * B, 0.13 * B, 0.03 * B, 24).rotateZ(Math.PI / 2);
      for (const z of zc) for (const sx of [-1, 1]) {
        const cp = part(new THREE.Mesh(plugGeo, M.bronze), 'block');
        cp.position.set(sx * 0.565 * B, (E.deck + bBot) / 2 - 0.1 * B, z);
        g.add(cp);
      }
    }
    const yTop = Math.max(Math.min(...banks.map((bk) => bBot * bk.b[1])), E.r + 0.6 * B);
    const geo = roundedBox(2 * caseR, yTop + caseR, zFront - zRear, 0.12 * B);
    boxWithEdges(layer.block, geo, cm, new V3(0, (yTop - caseR) / 2, zMid), 'crankcase');
    // the pan rail the sump bolts to
    const rail = part(new THREE.Mesh(roundedBox(2 * caseR + 0.14 * B, 0.09 * B, zFront - zRear + 0.1 * B, 0.03 * B), cm), 'crankcase');
    rail.position.set(0, -caseR + 0.045 * B, zMid);
    layer.block.add(rail);
    // main bearing caps between the throws
    const sorted = throws.map((t) => t.z).sort((a, b) => a - b);
    const mains = [sorted[0] - 0.6 * B, sorted[sorted.length - 1] + 0.6 * B];
    for (let i = 1; i < sorted.length; i++) if (sorted[i] - sorted[i - 1] > 0.6 * B) mains.push((sorted[i] + sorted[i - 1]) / 2);
    const capGeo = bevBox(1.1 * B, 0.36 * B, 0.18 * B);
    for (const z of mains) {
      const cap = part(new THREE.Mesh(capGeo, M.forged), 'mains');
      cap.position.set(0, -mainR - 0.18 * B, z);
      layer.block.add(cap);
      const brg = new THREE.Mesh(new THREE.TorusGeometry(mainR + 0.02 * B, 0.03 * B, 8, 32), M.bronze);
      brg.position.z = z;
      layer.block.add(brg);
      bolts(layer.block, [-0.4, 0.4].map((x) => [new V3(x * B, -mainR - 0.36 * B, z), new V3(0, -1, 0)]));
    }
    // ribs down the crankcase walls, as on a real casting
    const ribGeo = bevBox(0.05 * B, caseR * 0.9, 0.1 * B);
    for (const z of mains) for (const sx of [-1, 1]) {
      const rib = part(new THREE.Mesh(ribGeo, cm), 'crankcase');
      rib.position.set(sx * (caseR + 0.025 * B), -caseR * 0.45, z);
      layer.block.add(rib);
    }
    E.mains = mains;
  }

  // ------------------------------------------------------------ heads and covers
  const coverMat = M.cover;
  Object.assign(coverMat, {transparent: true, opacity: 0.22, depthWrite: false, side: THREE.DoubleSide});
  shell(coverMat);
  const headMat = shellMat('#acafb3');
  for (const bk of banks) {
    const g = bankGroup('head', bk, 1.3 * B);
    const len = bk.z1 - bk.z0 + 1.4 * B;
    const zc = (bk.z0 + bk.z1) / 2;
    boxWithEdges(g, roundedBox(2 * headHalf, headTop - E.deck, len, 0.06 * B), headMat, new V3(0, (headTop + E.deck) / 2, zc), 'head', {bank: bk.id});
    // the intake manifold's flange along the head, bolted between the ports
    {
      const fx = bk.sIn * (headHalf + 0.035 * B);
      const fl = part(new THREE.Mesh(roundedBox(0.07 * B, 0.52 * B, len - 0.3 * B, 0.025 * B), M.plenum), 'runner');
      fl.position.set(fx, E.deck + 0.3 * B, zc);
      g.add(fl);
      const nb = bk.cs.length + 1;
      for (const yy of [0.08, 0.52]) boltRow(g, new V3(fx + bk.sIn * 0.035 * B, E.deck + yy * B, bk.z0 - 0.59 * B), new V3(fx + bk.sIn * 0.035 * B, E.deck + yy * B, bk.z1 + 0.59 * B), nb, new V3(bk.sIn, 0, 0));
    }
    // the cam position sensor reads a target wheel on the cam nose, through the front of the head
    sensor(g, new V3(bk.sIn * 0.45 * B, headTop - 0.18 * B, zc + len / 2), new V3(0, 0, 1), 'cam-sensor', {bank: bk.id});
    const coverTop = camTopB + 0.06 * B;
    {
      // a flanged foot, walls drawing in, and a top rounded into them
      const cw = headHalf - 0.04 * B;
      const ch = coverTop - headTop;
      const wi = cw - 0.07 * B;
      const cr = Math.min(0.2 * B, ch * 0.55);
      const s = new THREE.Shape();
      s.moveTo(-cw, 0);
      s.lineTo(cw, 0);
      s.lineTo(cw, 0.05 * B);
      s.lineTo(wi, 0.08 * B);
      s.lineTo(wi, ch - cr);
      s.quadraticCurveTo(wi, ch, wi - cr, ch);
      s.lineTo(-(wi - cr), ch);
      s.quadraticCurveTo(-wi, ch, -wi, ch - cr);
      s.lineTo(-wi, 0.08 * B);
      s.lineTo(-cw, 0.05 * B);
      s.closePath();
      const bt = 0.04 * B;
      const geo = new THREE.ExtrudeGeometry(s, {depth: len - 0.06 * B - 2 * bt, bevelEnabled: true, bevelThickness: bt, bevelSize: 0.015 * B, bevelSegments: 3, curveSegments: 10});
      geo.translate(0, headTop, zc - (len - 0.06 * B - 2 * bt) / 2);
      boxWithEdges(g, geo, coverMat, new V3(), 'cover', {bank: bk.id});
    }
    bk.coverTop = coverTop;
    // the head gasket between block and head, with a fire ring per bore and holes for the head bolts
    const gk = part(new THREE.Mesh(gasketGeometry(B, 0.62 * B, bk.z0 - 0.62 * B, bk.z1 + 0.62 * B, bk.cs.map((c) => c.z), 0.012 * B), M.gasket), 'gasket', {bank: bk.id});
    gk.position.y = E.deck - 0.006 * B;
    g.add(gk);
    // four head bolts round every bore, seated on the head's top deck
    const hb = [];
    for (const c of bk.cs) for (const [x, dz] of [[-1, -0.5], [1, -0.5], [-1, 0.5], [1, 0.5]]) hb.push([new V3(x * (headHalf - 0.1 * B), headTop, c.z + dz * B * 1.08), new V3(0, 1, 0)]);
    bolts(g, hb);
    // the cover's own bolts down both edges, cast fins along the top, and the oil filler on the first bank
    const cb = [];
    const nz = Math.max(2, Math.round(len / (0.75 * B)));
    for (let i = 0; i <= nz; i++) for (const sx of [-1, 1]) cb.push([new V3(sx * (headHalf - 0.08 * B), headTop + 0.06 * B, zc - len / 2 + 0.15 * B + (i * (len - 0.3 * B)) / nz), new V3(0, 1, 0)]);
    bolts(g, cb);
    if (headHalf > 0.7 * B) for (const sx of [-1, 1]) {
      const fin = part(new THREE.Mesh(bevBox(0.035 * B, 0.07 * B, len * 0.82), coverMat), 'cover', {bank: bk.id});
      fin.position.set(sx * (headHalf - 0.42 * B), coverTop + 0.03 * B, zc);
      g.add(fin);
    }
    if (bk === banks[0]) {
      const cap = part(new THREE.Group(), 'oil-cap');
      const base = new THREE.Mesh(new THREE.CylinderGeometry(0.17 * B, 0.17 * B, 0.08 * B, 24), M.black);
      const grip = new THREE.Mesh(bevBox(0.3 * B, 0.07 * B, 0.06 * B), M.black);
      grip.position.y = 0.07 * B;
      cap.add(base, grip);
      cap.position.set(0, coverTop + 0.04 * B, bk.z1 + 0.5 * B);
      g.add(cap);
    }
  }

  // ------------------------------------------------------------ valvetrain
  const springGeo = (() => {
    const pts = [];
    const turns = 6;
    for (let i = 0; i <= turns * 24; i++) {
      const a = (i / 24) * Math.PI * 2;
      pts.push(new V3(0.1 * B * Math.cos(a), i / (turns * 24), 0.1 * B * Math.sin(a)));
    }
    return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), turns * 24, 0.013 * B, 6, false);
  })();
  const valveGeo = (d) => lathe([[0, 0], [d / 2, 0], [d / 2, 0.03 * B], [0.09 * d, 0.16 * B], [0.07 * d, 0.16 * B], [0.07 * d, Ls], [0, Ls]], 28);
  const vGeo = {in: valveGeo(dIn), ex: valveGeo(dEx)};
  const bucketGeo = new THREE.CylinderGeometry(0.13 * B, 0.13 * B, bucketH, 24).translate(0, bucketH / 2, 0);
  const retGeo = new THREE.CylinderGeometry(0.1 * B, 0.07 * B, 0.04 * B, 20);
  const lift = (kind, ps) => (kind === 'in' ? E.liftIn(ps) : E.liftEx(ps));
  const lobeGeo = (kappa, kind, fire, base, Lc, t) => {
    const s = new THREE.Shape();
    for (let i = 0; i <= 180; i++) {
      const psi = i * 2;
      const R = base + Lc * lift(kind, mod(2 * (kappa - psi) - fire, 720));
      const x = R * Math.sin(psi * D2R);
      const y = R * Math.cos(psi * D2R);
      i ? s.lineTo(x, y) : s.moveTo(x, y);
    }
    return new THREE.ExtrudeGeometry(s, {depth: t, bevelEnabled: false, curveSegments: 2}).translate(0, 0, -t / 2);
  };
  const valves = []; // {mesh, spring, bucket, ret, kind, seat:[p,b], u:[x,y], z, cyl, rocker?}
  const cams = [];
  for (const bk of banks) {
    const g = (bk.vg = bankGroup('valvetrain', bk, 2.3 * B));
    for (const kind of ['in', 'ex']) {
      const side = kind === 'in' ? bk.sIn : bk.sEx;
      const u = [side * Math.sin(gam), Math.cos(gam)];
      for (const c of bk.cs) {
        for (const s of seats(kind, side)) {
          const v = part(new THREE.Mesh(vGeo[kind], M[kind === 'in' ? 'vin' : 'vex']), kind === 'in' ? 'valve-in' : 'valve-ex', {cyl: c.n});
          v.rotation.z = -side * gam;
          g.add(v);
          const sp = part(new THREE.Mesh(springGeo, M.spring), 'spring', {cyl: c.n});
          sp.rotation.z = -side * gam;
          g.add(sp);
          // the spring seat washer and the rubber stem seal on top of the valve guide, at the spring's base
          const at0 = (d) => new V3(s.p + u[0] * d, E.deck + u[1] * d, c.z + s.z);
          const seat = part(new THREE.Mesh(new THREE.CylinderGeometry(0.115 * B, 0.115 * B, 0.012 * B, 20), M.steel), 'stem-seal', {cyl: c.n});
          seat.position.copy(at0(0.3 * B - 0.006 * B));
          seat.rotation.z = -side * gam;
          const seal = part(new THREE.Mesh(new THREE.CylinderGeometry(0.045 * B, 0.05 * B, 0.06 * B, 16), M.rubber), 'stem-seal', {cyl: c.n});
          seal.position.copy(at0(0.3 * B + 0.03 * B));
          seal.rotation.z = -side * gam;
          g.add(seat, seal);
          let bucket = null;
          let ret = null;
          if (!ohv) {
            bucket = part(new THREE.Mesh(bucketGeo, M.cam), 'bucket', {cyl: c.n});
            bucket.rotation.z = -side * gam;
            g.add(bucket);
          } else {
            ret = new THREE.Mesh(retGeo, M.steel);
            // the split collets (keepers) that lock the retainer to the valve stem
            const keep = new THREE.Mesh(new THREE.CylinderGeometry(0.035 * B, 0.05 * B, 0.05 * B, 12), M.steel);
            keep.position.y = 0.04 * B;
            ret.add(keep);
            ret.rotation.z = -side * gam;
            g.add(ret);
          }
          valves.push({v, sp, bucket, ret, kind, seat: [s.p, E.deck], u, z: c.z + s.z, c, bk, d: kind === 'in' ? dIn : dEx});
        }
      }
    }
    if (!ohv) {
      // overhead cams: one per kind (DOHC), or one carrying both (SOHC)
      for (const kinds of sohc ? [['in', 'ex']] : [['in'], ['ex']]) {
        const [cx, cy] = camCenter(bk, kinds[0]);
        const cam = part(new THREE.Group(), sohc ? 'cam-sohc' : kinds[0] === 'in' ? 'cam-in' : 'cam-ex', {bank: bk.id});
        cam.position.set(cx, cy, 0);
        const zf = zFront + 0.2 * B;
        const zr = bk.z0 - 0.7 * B;
        const sh = new THREE.Mesh(new THREE.CylinderGeometry(0.1 * B, 0.1 * B, zf - zr, 20), M.cam);
        sh.rotation.x = Math.PI / 2;
        sh.position.z = (zf + zr) / 2;
        cam.add(sh);
        for (const vv of valves.filter((x) => x.bk === bk && kinds.includes(x.kind))) {
          const kappa = Math.atan2(-vv.u[0], -vv.u[1]) / D2R;
          const lobe = new THREE.Mesh(lobeGeo(kappa, vv.kind, vv.c.fire, camBase, liftMax[vv.kind] * (vv.d / (vv.kind === 'in' ? dIn : dEx)), 0.11 * B), M.cam);
          lobe.position.z = vv.z;
          cam.add(lobe);
        }
        // journals in the head
        for (const c of bk.cs) {
          const jz = c.z + 0.55 * B;
          const capM = part(new THREE.Mesh(bevBox(0.46 * B, 0.18 * B, 0.13 * B), M.alu), 'cam-cap', {bank: bk.id});
          capM.position.set(cx, cy + 0.07 * B, jz);
          g.add(capM);
          const jr = new THREE.Mesh(new THREE.CylinderGeometry(0.13 * B, 0.13 * B, 0.12 * B, 20), M.alu);
          jr.rotation.x = Math.PI / 2;
          jr.position.set(cx, cy, jz);
          g.add(jr);
          bolts(g, [-0.17, 0.17].map((x) => [new V3(cx + x * B, cy + 0.16 * B, jz), new V3(0, 1, 0)]));
        }
        g.add(cam);
        cams.push({cam, bk, world: W(bk, cx, cy)});
        movers.push((th) => (cam.rotation.z = -(th / 2) * D2R));
      }
    }
  }
  // pushrod engines: one cam in the block, a lifter and pushrod per valve, a rocker on the head
  if (ohv) {
    const yc = Math.max(1.15 * B, E.r + pinR * 1.35 + 0.42 * B);
    const g = worldGroup('valvetrain', new V3());
    const cam = part(new THREE.Group(), 'cam-block');
    cam.position.set(0, yc, 0);
    const sh = new THREE.Mesh(new THREE.CylinderGeometry(0.12 * B, 0.12 * B, zFront - zRear + 0.6 * B, 20), M.cam);
    sh.rotation.x = Math.PI / 2;
    sh.position.z = zMid + 0.3 * B;
    cam.add(sh);
    g.add(cam);
    cams.push({cam, block: true, world: new V3(0, yc, 0)});
    movers.push((th) => (cam.rotation.z = -(th / 2) * D2R));
    const base = 0.2 * B;
    const lv = 0.3 * B;
    const lp = lv / rr;
    const pivotB = E.deck + Ls + 0.06 * B;
    for (const vv of valves) {
      const bk = vv.bk;
      const side = bk.sIn; // pushrods come up from the valley
      const cupRest = W(bk, side * (lv + lp), pivotB, vv.z);
      const dir = new V3(cupRest.x, cupRest.y - yc, 0).normalize();
      const kappa = Math.atan2(dir.x, dir.y) / D2R;
      const Lc = liftMax[vv.kind] / rr;
      const lobe = new THREE.Mesh(lobeGeo(kappa, vv.kind, vv.c.fire, base, Lc, 0.12 * B), M.cam);
      lobe.position.z = vv.z;
      cam.add(lobe);
      const lifter = part(new THREE.Mesh(rod01(0.08 * B), M.steel), 'lifter', {cyl: vv.c.n});
      const push = part(new THREE.Mesh(rod01(0.025 * B, 10), M.steel), 'pushrod', {cyl: vv.c.n});
      g.add(lifter, push);
      // the rocker: a beam about its pivot, valve end inboard of the pivot by lv, cup end outboard by lp
      const vg = bk.vg;
      const rocker = part(new THREE.Group(), 'rocker', {cyl: vv.c.n});
      rocker.position.set(side * lv, pivotB, vv.z);
      const beam = new THREE.Mesh(bevBox(lv + lp + 0.08 * B, 0.07 * B, 0.08 * B), M.forged);
      beam.position.x = side * (lp - lv) / 2;
      const piv = new THREE.Mesh(new THREE.CylinderGeometry(0.05 * B, 0.05 * B, 0.12 * B, 12).rotateX(Math.PI / 2), M.steel);
      rocker.add(beam, piv);
      vg.add(rocker);
      Object.assign(vv, {rocker, lifter, push, dir, yc, base, Lc, side, lv, lp, pivotB});
    }
  }
  movers.push((th) => {
    for (const vv of valves) {
      const ps = E.psi(vv.c, th);
      const L = lift(vv.kind, ps) * liftMax[vv.kind];
      const [px, py] = vv.seat;
      const at = (d) => new V3(px + vv.u[0] * d, py + vv.u[1] * d, vv.z);
      vv.v.position.copy(at(-L));
      vv.sp.position.copy(at(0.3 * B));
      vv.sp.scale.y = Ls - L - 0.08 * B - 0.3 * B;
      if (vv.bucket) vv.bucket.position.copy(at(Ls - L));
      if (vv.ret) vv.ret.position.copy(at(Ls - L - 0.08 * B));
      if (vv.rocker) {
        const a = Math.asin(Math.min(1, L / vv.lv));
        vv.rocker.rotation.z = vv.side * a;
        const camL = L / rr;
        const c0 = new V3(0, vv.yc, vv.z);
        const lt0 = c0.clone().addScaledVector(vv.dir, vv.base + camL);
        const lt1 = lt0.clone().addScaledVector(vv.dir, 0.38 * B);
        along(vv.lifter, lt0, lt1);
        const cup = W(vv.bk, vv.side * (vv.lv + vv.lp * Math.cos(a)), vv.pivotB + vv.lp * Math.sin(a), vv.z);
        along(vv.push, lt1, cup);
      }
    }
  });

  // ------------------------------------------------------------ cam drive: sprockets at 2:1 and a moving chain
  {
    const zT = zFront + 0.12 * B;
    const g = worldGroup('timing', new V3(0, 0, 1.6 * B));
    const rc = 0.22 * B;
    const circles = [{x: 0, y: 0, r: rc}];
    const crankSp = part(new THREE.Mesh(gearGeo(rc, 18, 0.12 * B), M.steel), 'sprockets');
    crankSp.position.set(0, 0, zT);
    g.add(crankSp);
    movers.push((th) => (crankSp.rotation.z = -th * D2R));
    for (const cm of cams) {
      const sp = part(new THREE.Mesh(gearGeo(2 * rc, 36, 0.12 * B), M.steel), 'sprockets');
      sp.position.set(cm.world.x, cm.world.y, zT);
      g.add(sp);
      // a vane-type cam phaser on the intake cam of a twin-cam engine: oil pressure turns the cam against its sprocket
      if (cm.cam.userData.pick?.id === 'cam-in') {
        const ph = part(new THREE.Group(), 'phaser');
        const body = new THREE.Mesh(new THREE.CylinderGeometry(1.45 * rc, 1.45 * rc, 0.16 * B, 40).rotateX(Math.PI / 2), M.aluMachined);
        const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.55 * rc, 0.55 * rc, 0.05 * B, 24).rotateX(Math.PI / 2), M.bolt);
        cap.position.z = 0.1 * B;
        ph.add(body, cap);
        bolts(ph, [0, 1, 2, 3].map((k) => {
          const a = (k * Math.PI) / 2 + Math.PI / 4;
          return [new V3(1.1 * rc * Math.cos(a), 1.1 * rc * Math.sin(a), 0.08 * B), new V3(0, 0, 1)];
        }));
        ph.position.set(cm.world.x, cm.world.y, zT + 0.15 * B);
        g.add(ph);
        movers.push((th) => (ph.rotation.z = -(th / 2) * D2R));
      }
      circles.push({x: cm.world.x, y: cm.world.y, r: 2 * rc});
      movers.push((th) => (sp.rotation.z = -(th / 2) * D2R));
    }
    const poly = hull(circles);
    const path = pathTable(poly);
    // a roller chain: n pins round the path, alternating inner and outer plate pairs between them
    const pitch = 0.11 * B;
    const n = 2 * Math.floor(path.L / pitch / 2);
    const step = path.L / n;
    const plates = part(new THREE.InstancedMesh(chainPlateGeometry(step, 0.012 * B), M.chain, 2 * n), 'chain');
    const pins = part(new THREE.InstancedMesh(new THREE.CylinderGeometry(0.02 * B, 0.02 * B, 0.17 * B, 8).rotateX(Math.PI / 2), M.pin, n), 'chain');
    plates.frustumCulled = pins.frustumCulled = false;
    g.add(plates, pins);
    const m4 = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const one = new V3(1, 1, 1);
    const zAxis = new V3(0, 0, 1);
    const P = new V3();
    const joints = new Array(n);
    movers.push((th) => {
      // the crank sprocket's pitch line moves th·rc; the chain goes clockwise seen from the front, like the crank
      const travel = th * D2R * rc;
      // the pattern repeats every two pitches, so the inner and outer plates swap smoothly
      const shift = Math.floor(travel / (2 * step)) * 2;
      for (let i = 0; i < n; i++) joints[i] = path.at(i * step - travel + shift * step);
      for (let i = 0; i < n; i++) {
        const a = joints[i];
        const b = joints[(i + 1) % n];
        q.setFromAxisAngle(zAxis, 0);
        pins.setMatrixAt(i, m4.compose(P.set(a[0], a[1], zT), q, one));
        q.setFromAxisAngle(zAxis, Math.atan2(b[1] - a[1], b[0] - a[0]));
        const zo = i % 2 ? 0.07 * B : 0.045 * B;
        const mx = (a[0] + b[0]) / 2;
        const my = (a[1] + b[1]) / 2;
        plates.setMatrixAt(2 * i, m4.compose(P.set(mx, my, zT + zo), q, one));
        plates.setMatrixAt(2 * i + 1, m4.compose(P.set(mx, my, zT - zo), q, one));
      }
      pins.instanceMatrix.needsUpdate = true;
      plates.instanceMatrix.needsUpdate = true;
    });
    // nylon-faced guides on the straight runs, and a hydraulic tensioner pushing the longest one
    const cx = poly.reduce((a, q2) => a + q2[0], 0) / poly.length;
    const cy = poly.reduce((a, q2) => a + q2[1], 0) / poly.length;
    const runs = poly.map((a, i) => [a, poly[(i + 1) % poly.length]]).filter(([a, b]) => Math.hypot(b[0] - a[0], b[1] - a[1]) > 1.1 * B);
    runs.sort((u, v) => Math.hypot(v[1][0] - v[0][0], v[1][1] - v[0][1]) - Math.hypot(u[1][0] - u[0][0], u[1][1] - u[0][1]));
    runs.forEach(([a, b], k) => {
      const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
      const mx = (a[0] + b[0]) / 2;
      const my = (a[1] + b[1]) / 2;
      let nx = -(b[1] - a[1]) / len;
      let ny = (b[0] - a[0]) / len;
      if (nx * (cx - mx) + ny * (cy - my) < 0) {
        nx = -nx;
        ny = -ny;
      }
      const guide = part(new THREE.Mesh(bevBox(len * 0.7, 0.07 * B, 0.2 * B), M.black), k === 0 ? 'tensioner' : 'guide');
      guide.position.set(mx + nx * 0.06 * B, my + ny * 0.06 * B, zT);
      guide.rotation.z = Math.atan2(b[1] - a[1], b[0] - a[0]);
      g.add(guide);
      if (k === 0) {
        const body = part(new THREE.Mesh(new THREE.CylinderGeometry(0.09 * B, 0.09 * B, 0.36 * B, 16), M.alu), 'tensioner');
        body.position.set(mx + nx * 0.3 * B, my + ny * 0.3 * B, zT);
        body.rotation.z = -Math.atan2(nx, ny);
        g.add(body);
      }
    });
    E.timingLength = path.L;
    // the cover over the whole drive, cast to its outline with a margin and bolted round the edge; it lifts off
    // ahead of the chain when the engine opens up
    const cg = worldGroup('timing', new V3(0, 0, 2.3 * B));
    const outline = hull([...circles.map((q2) => ({...q2, r: q2.r + 0.24 * B})), {x: 0, y: 0, r: 0.75 * B}]);
    const depth = 0.3 * B;
    const coverGeo = new THREE.ExtrudeGeometry(new THREE.Shape(outline.map(([x, y]) => new THREE.Vector2(x, y))), {depth, bevelEnabled: true, bevelThickness: 0.05 * B, bevelSize: 0.05 * B, bevelSegments: 3, curveSegments: 8});
    coverGeo.translate(0, 0, zFront - 0.06 * B);
    boxWithEdges(cg, coverGeo, shellMat('#a4a7ab'), new V3(), 'timing-cover');
    const ox = outline.reduce((a, q2) => a + q2[0], 0) / outline.length;
    const oy = outline.reduce((a, q2) => a + q2[1], 0) / outline.length;
    const op = pathTable(outline);
    const nb = Math.max(8, Math.round(op.L / (0.8 * B)));
    const tb = [];
    for (let i = 0; i < nb; i++) {
      const [x, y] = op.at((i * op.L) / nb);
      const d = Math.hypot(x - ox, y - oy) || 1;
      tb.push([new V3(x - ((x - ox) / d) * 0.12 * B, y - ((y - oy) / d) * 0.12 * B, zFront - 0.06 * B + depth + 0.05 * B), new V3(0, 0, 1)]);
    }
    bolts(cg, tb);
    // cast bosses over each cam nose and the crank seal, joined by a stiffening rib, so the face is not a slab
    const coverFace = zFront - 0.06 * B + depth + 0.05 * B;
    const cmCover = shellMat('#a4a7ab');
    for (const c2 of circles) {
      const crank0 = c2.x === 0 && c2.y === 0;
      const r2 = crank0 ? 0.42 * B : c2.r * 0.62;
      const boss = part(new THREE.Mesh(new THREE.CylinderGeometry(r2, r2 + 0.04 * B, 0.12 * B, 40).rotateX(Math.PI / 2), cmCover), 'timing-cover');
      boss.position.set(c2.x, c2.y, coverFace + 0.06 * B);
      cg.add(boss);
      if (!crank0) {
        const rib = part(new THREE.Mesh(roundedBox(0.09 * B, Math.hypot(c2.x, c2.y) - 0.5 * B, 0.07 * B, 0.03 * B), cmCover), 'timing-cover');
        rib.position.set(c2.x / 2, c2.y / 2, coverFace + 0.035 * B);
        rib.rotation.z = -Math.atan2(c2.x, c2.y);
        cg.add(rib);
      }
    }
    const ca = 40 * D2R;
    sensor(cg, new V3(0.8 * B * Math.sin(ca), -0.8 * B * Math.cos(ca), zFront + 0.1 * B), new V3(Math.sin(ca), -Math.cos(ca), 0), 'crank-sensor');
  }

  // ------------------------------------------------------------ accessory drive: crank pulley, water pump, alternator
  {
    const zA = zFront + 0.62 * B;
    const g = worldGroup('accessory', new V3(0, 0, 2.6 * B));
    const topY = Math.max(...banks.map((bk) => W(bk, 0, E.deck).y));
    const Rc = 0.55 * B;
    const pul = [
      {id: 'pulley-crank', x: 0, y: 0, r: Rc},
      {id: 'water-pump', x: 0, y: Math.max(1.5 * B, 0.55 * topY), r: 0.4 * B},
      {id: 'alternator', x: caseR + 0.4 * B, y: 0.9 * B, r: 0.26 * B},
      {id: 'idler', x: -(caseR + 0.15 * B), y: 0.7 * B, r: 0.22 * B},
    ];
    // a car engine also turns the air-conditioning compressor; a bike single does not
    if (E.cyl.length >= 3) pul.push({id: 'ac-compressor', x: -(caseR + 0.35 * B), y: -0.55 * B, r: 0.3 * B});
    for (const p of pul) {
      const m = part(new THREE.Group(), p.id);
      const disc = new THREE.Mesh(p.id === 'idler' ? new THREE.CylinderGeometry(p.r, p.r, 0.16 * B, 32).rotateX(Math.PI / 2) : polyVGeometry(p.r, 0.16 * B), p.id === 'pulley-crank' ? M.forged : M.aluMachined);
      const hub = new THREE.Mesh(new THREE.CylinderGeometry(p.r * 0.32, p.r * 0.32, 0.2 * B, 6).rotateX(Math.PI / 2), M.bolt);
      // a pressed web with lightening holes, which is also what lets the rotation read
      if (p.id !== 'idler') {
        const web = new THREE.Shape();
        web.absarc(0, 0, p.r * 0.88, 0, Math.PI * 2, false);
        const nh = p.id === 'pulley-crank' ? 6 : 5;
        for (let i = 0; i < nh; i++) {
          const a = (i / nh) * Math.PI * 2;
          const h = new THREE.Path();
          h.absarc(0.58 * p.r * Math.cos(a), 0.58 * p.r * Math.sin(a), 0.15 * p.r, 0, Math.PI * 2, true);
          web.holes.push(h);
        }
        const wg = new THREE.ExtrudeGeometry(web, {depth: 0.04 * B, bevelEnabled: true, bevelThickness: 0.012 * B, bevelSize: 0.012 * B, bevelSegments: 2, curveSegments: 24}).translate(0, 0, 0.02 * B);
        m.add(new THREE.Mesh(wg, p.id === 'pulley-crank' ? M.forged : M.aluMachined));
      }
      m.add(disc, hub);
      if (p.id === 'pulley-crank') {
        const damper = new THREE.Mesh(new THREE.TorusGeometry(p.r * 0.78, 0.035 * B, 8, 48), M.rubber);
        damper.position.z = 0.09 * B;
        m.add(damper);
      }
      m.position.set(p.x, p.y, zA);
      g.add(m);
      if (p.id === 'alternator') {
        const body = new THREE.Mesh(new THREE.CylinderGeometry(0.42 * B, 0.42 * B, 0.7 * B, 24), M.alu);
        body.rotation.x = Math.PI / 2;
        body.position.set(p.x, p.y, zA - 0.45 * B);
        part(body, 'alternator');
        g.add(body);
        // the case's cooling slots, the fan behind the pulley and the B+ terminal at the back
        for (let i = 0; i < 5; i++) {
          const fin = part(new THREE.Mesh(new THREE.TorusGeometry(0.425 * B, 0.018 * B, 6, 40), M.aluMachined), 'alternator');
          fin.position.set(p.x, p.y, zA - 0.2 * B - i * 0.11 * B);
          g.add(fin);
        }
        const fan = part(new THREE.Mesh(gearGeo(0.36 * B, 12, 0.04 * B, 0.35), M.steel), 'alternator');
        fan.position.set(p.x, p.y, zA - 0.11 * B);
        g.add(fan);
        movers.push((th) => (fan.rotation.z = -th * (Rc / p.r) * D2R));
        const term = part(new THREE.Mesh(new THREE.CylinderGeometry(0.05 * B, 0.05 * B, 0.12 * B, 6).rotateX(Math.PI / 2), M.bronze), 'alternator');
        term.position.set(p.x + 0.2 * B, p.y + 0.15 * B, zA - 0.86 * B);
        g.add(term);
        boltRow(g, new V3(p.x - 0.32 * B, p.y - 0.32 * B, zA - 0.82 * B), new V3(p.x + 0.32 * B, p.y - 0.32 * B, zA - 0.82 * B), 2, new V3(0, 0, -1));
      }
      if (p.id === 'ac-compressor') {
        const body = part(new THREE.Group(), 'ac-compressor');
        const can = new THREE.Mesh(new THREE.CylinderGeometry(0.4 * B, 0.4 * B, 0.5 * B, 28), M.aluMachined);
        can.rotation.x = Math.PI / 2;
        const head = new THREE.Mesh(bevBox(0.34 * B, 0.22 * B, 0.2 * B), M.alu);
        head.position.set(0, 0.42 * B, -0.1 * B);
        const ports2 = new THREE.Mesh(new THREE.CylinderGeometry(0.06 * B, 0.06 * B, 0.18 * B, 12), M.aluMachined);
        ports2.position.set(0, 0.55 * B, -0.1 * B);
        body.add(can, head, ports2);
        body.position.set(p.x, p.y, zA - 0.4 * B);
        g.add(body);
      }
      if (p.id === 'water-pump') {
        bolts(g, Array.from({length: 6}, (_, i) => {
          const a = (i / 6) * Math.PI * 2;
          return [new V3(p.x + 0.4 * B * Math.cos(a), p.y + 0.4 * B * Math.sin(a), zA - 0.48 * B), new V3(0, 0, 1)];
        }));
        const body = new THREE.Mesh(new THREE.CylinderGeometry(0.3 * B, 0.36 * B, 0.4 * B, 20), M.alu);
        body.rotation.x = Math.PI / 2;
        body.position.set(p.x, p.y, zA - 0.3 * B);
        part(body, 'water-pump');
        g.add(body);
      }
      // a belt cannot slip: every pulley's rim speed is the crank pulley's
      const ratio = Rc / p.r;
      movers.push((th) => (m.rotation.z = -th * ratio * D2R));
    }
    const poly = hull(pul);
    const belt = part(new THREE.Mesh(tube(poly.map(([x, y]) => new V3(x, y, zA)), 0.035 * B, true, 200), M.rubber), 'belt');
    g.add(belt);
  }

  // ------------------------------------------------------------ lubrication
  {
    const g = worldGroup('lube', new V3(0, -1.8 * B, 0));
    const dry = hw.oil === 'dry';
    const top = -caseR;
    const depth = dry ? 0.28 * B : 0.85 * B;
    const s = new THREE.Shape();
    s.moveTo(-caseR, 0);
    s.lineTo(caseR, 0);
    s.lineTo(caseR * 0.82, -depth);
    s.lineTo(-caseR * 0.82, -depth);
    s.closePath();
    const bv = 0.05 * B;
    const panGeo = new THREE.ExtrudeGeometry(s, {depth: zFront - zRear - 2 * bv, bevelEnabled: true, bevelThickness: bv, bevelSize: 0.02 * B, bevelSegments: 3}).translate(0, top, zRear + bv);
    const panMat = shellMat('#5d646d');
    const sumpId = dry ? 'sump-dry' : 'sump-wet';
    boxWithEdges(g, panGeo, panMat, new V3(), sumpId);
    const flange = part(new THREE.Mesh(roundedBox(2 * caseR + 0.14 * B, 0.06 * B, zFront - zRear + 0.1 * B, 0.02 * B), panMat), sumpId);
    flange.position.set(0, top - 0.03 * B, zMid);
    g.add(flange);
    const nsb = Math.max(4, Math.round((zFront - zRear) / (0.7 * B)));
    for (const sx of [-1, 1]) boltRow(g, new V3(sx * (caseR + 0.03 * B), top - 0.06 * B, zRear + 0.15 * B), new V3(sx * (caseR + 0.03 * B), top - 0.06 * B, zFront - 0.15 * B), nsb, new V3(0, -1, 0));
    // cast ribs across the floor for stiffness and cooling, and the drain plug at the low point
    for (let i = 1; i < nsb; i++) {
      const rib = part(new THREE.Mesh(roundedBox(caseR * 1.5, 0.06 * B, 0.05 * B, 0.02 * B), panMat), sumpId);
      rib.position.set(0, top - depth - 0.03 * B, zRear + ((zFront - zRear) * i) / nsb);
      g.add(rib);
    }
    bolts(g, [[new V3(0.3 * caseR, top - depth - 0.02 * B, zRear + 0.4 * B), new V3(0, -1, 0)]]);
    const oilH = depth * (dry ? 0.25 : 0.45);
    const oil = part(new THREE.Mesh(bevBox(caseR * 1.6, oilH, zFront - zRear - 0.1 * B), M.oil), dry ? 'sump-dry' : 'sump-wet');
    oil.position.set(0, top - depth + oilH / 2, zMid);
    g.add(oil);
    // the pump on the crank nose: a gerotor whose inner rotor is keyed to the crank
    const zP = zFront + 0.02 * B;
    const housing = part(new THREE.Mesh(new THREE.CylinderGeometry(0.5 * B, 0.5 * B, 0.1 * B, 32), M.alu), 'oil-pump');
    housing.rotation.x = Math.PI / 2;
    housing.position.set(0, 0, zP - 0.07 * B);
    g.add(housing);
    const rotor = part(new THREE.Mesh(gearGeo(0.34 * B, 6, 0.08 * B, 0.3), M.steel), 'oil-pump');
    rotor.position.set(0, 0, zP + 0.02 * B);
    g.add(rotor);
    movers.push((th) => (rotor.rotation.z = -th * D2R));
    oilLine(g, [new V3(0, -0.5 * B, zP - 0.1 * B), new V3(0, top - 0.2 * B, zFront - 0.3 * B), new V3(0, top - depth + 0.12 * B, zMid + 0.4 * B)], 0.06 * B, 'pickup');
    const strainer = part(new THREE.Mesh(new THREE.CylinderGeometry(0.22 * B, 0.22 * B, 0.05 * B, 20), M.steel), 'pickup');
    strainer.position.set(0, top - depth + 0.08 * B, zMid + 0.4 * B);
    g.add(strainer);
    // filter, then the main gallery along the block with a feed to every main bearing, and a riser to each head
    const fx = caseR + 0.28 * B;
    const filter = part(new THREE.Mesh(filterGeometry(B), M.filter), 'filter');
    filter.rotation.z = -Math.PI / 2;
    filter.position.set(fx - 0.2 * B, -0.35 * B, zFront - 0.6 * B);
    g.add(filter);
    sensor(g, new V3(caseR + 0.02 * B, 0.2 * B, zFront - 1.05 * B), new V3(1, 0, 0), 'oil-sensor');
    const gy = -0.1 * B;
    const gx = caseR - 0.12 * B;
    oilLine(g, [new V3(0.3 * B, -0.3 * B, zP - 0.1 * B), new V3(fx - 0.2 * B, -0.35 * B, zFront - 0.3 * B), new V3(fx - 0.2 * B, -0.35 * B, zFront - 0.6 * B)], 0.05 * B, 'gallery');
    oilLine(g, [new V3(gx, gy, zFront - 0.6 * B), new V3(gx, gy, zMid), new V3(gx, gy, zRear + 0.2 * B)], 0.05 * B, 'gallery');
    for (const z of E.mains) oilLine(g, [new V3(gx, gy, z), new V3(gx * 0.5, -0.45 * B, z), new V3(0.05 * B, -mainR - 0.05 * B, z)], 0.03 * B, 'gallery');
    for (const bk of banks) {
      const cc = cams.find((x) => x.bk === bk);
      const end = cc ? cc.world.clone().setZ(bk.z1 + 0.3 * B) : W(bk, 0, E.deck + Ls, bk.z1 + 0.3 * B);
      oilLine(g, [new V3(gx, gy, zRear + 0.2 * B), new V3(gx * 0.6, gy + 0.6 * B, zRear + 0.1 * B), W(bk, 0, E.deck - 0.2 * B, zRear + 0.4 * B), end], 0.035 * B, 'gallery');
    }
    if (dry) {
      const tx = -(caseR + 1.1 * B);
      const tank = part(new THREE.Group(), 'oil-tank');
      const body = new THREE.Mesh(new THREE.CylinderGeometry(0.5 * B, 0.5 * B, 2.4 * B, 32), shellMat('#c9ccd0'));
      const lvl = new THREE.Mesh(new THREE.CylinderGeometry(0.47 * B, 0.47 * B, 1.4 * B, 32), M.oil);
      lvl.position.y = -0.48 * B;
      const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.16 * B, 0.16 * B, 0.12 * B, 16), M.black);
      cap.position.y = 1.26 * B;
      tank.add(body, lvl, cap);
      tank.position.set(tx, 0.2 * B, zFront - 1.0 * B);
      g.add(tank);
      const scav = part(new THREE.Mesh(bevBox(0.5 * B, 0.4 * B, 1.0 * B), M.alu), 'scavenge');
      scav.position.set(-(caseR + 0.3 * B), top - 0.2 * B, zFront - 0.4 * B);
      g.add(scav);
      oilLine(g, [new V3(-caseR * 0.6, top - depth * 0.6, zMid), new V3(-(caseR + 0.1 * B), top - depth * 0.4, zMid + 0.6 * B), scav.position.clone().add(new V3(0, 0, -0.4 * B))], 0.05 * B, 'scavenge');
      oilLine(g, [scav.position.clone().add(new V3(-0.25 * B, 0, 0)), new V3(tx + 0.2 * B, 1.0 * B, zFront - 0.6 * B), new V3(tx, 1.45 * B, zFront - 1.0 * B)], 0.05 * B, 'oil-tank');
      oilLine(g, [new V3(tx, -1.0 * B, zFront - 1.0 * B), new V3(tx + 0.6 * B, -0.8 * B, zFront - 0.4 * B), new V3(-0.3 * B, -0.3 * B, zP - 0.1 * B)], 0.05 * B, 'oil-tank');
    } else {
      const dip = part(new THREE.Mesh(tube([new V3(-caseR + 0.1 * B, top - 0.4 * B, zFront - 0.8 * B), new V3(-caseR - 0.15 * B, 0.2 * B, zFront - 0.8 * B), new V3(-caseR - 0.05 * B, 1.6 * B, zFront - 0.8 * B)], 0.03 * B), M.steel), 'dipstick');
      g.add(dip);
      const handle = new THREE.Mesh(new THREE.TorusGeometry(0.08 * B, 0.025 * B, 8, 20), std(ACCENT, 0.2, 0.5));
      handle.position.set(-caseR - 0.05 * B, 1.7 * B, zFront - 0.8 * B);
      g.add(handle);
    }
  }

  // ------------------------------------------------------------ intake
  const ports = (bk, side) => bk.cs.map((c) => ({c, inside: W(bk, side * 0.35 * B, E.deck + 0.22 * B, c.z), exit: W(bk, side * headHalf, E.deck + 0.3 * B, c.z)}));
  let throttle = null;
  {
    const exV = multi ? new V3(0, 2.2 * B, 0) : W(banks[0], banks[0].sIn * 1.6 * B, 0.4 * B);
    const g = worldGroup('intake', exV);
    const plenR = 0.5 * B;
    let plenumAt;
    const allPorts = banks.flatMap((bk) => ports(bk, bk.sIn).map((p) => ({...p, bk})));
    if (multi) {
      const yTop = Math.max(...allPorts.map((p) => p.exit.y)) + 1.0 * B;
      plenumAt = (z) => new V3(0, yTop, z);
    } else {
      const bk = banks[0];
      plenumAt = (z) => W(bk, bk.sIn * (headHalf + 1.25 * B), E.deck + 0.05 * B, z);
    }
    for (const p of allPorts) {
      const n = new V3().subVectors(p.exit, p.inside).normalize();
      const end = plenumAt(p.c.z);
      const mid = p.exit.clone().addScaledVector(n, 0.5 * B).lerp(end, 0.35);
      const runner = part(new THREE.Mesh(tube([p.inside, p.exit, mid, end], 0.2 * B), M.plenum), 'runner', {cyl: p.c.n});
      g.add(runner);
      p.injAt = p.exit.clone().addScaledVector(n, 0.3 * B);
      p.n = n;
    }
    const z0 = Math.min(...zs) - 0.6 * B;
    const z1 = Math.max(...zs) + 0.8 * B;
    const a = plenumAt(z0);
    const b = plenumAt(z1);
    // a cast plenum: broad and low over a V's valley, tall and narrow beside an inline head, banded by ribs
    const pw = (multi ? 1.7 : 1.05) * B;
    const ph = (multi ? 0.85 : 1.15) * B;
    const plen = part(new THREE.Mesh(roundedBox(pw, ph, z1 - z0, 0.28 * B, 4), M.plenum), 'plenum');
    plen.position.copy(a.clone().lerp(b, 0.5));
    g.add(plen);
    const nr = Math.max(2, Math.round((z1 - z0) / (1.1 * B)));
    for (let i = 1; i < nr; i++) {
      const band = part(new THREE.Mesh(roundedBox(pw + 0.05 * B, ph + 0.05 * B, 0.06 * B, 0.29 * B, 4), M.plenum), 'plenum');
      band.position.copy(a.clone().lerp(b, i / nr));
      g.add(band);
    }
    sensor(g, plen.position.clone().add(new V3(0.25 * B, ph / 2, (z1 - z0) * 0.25)), new V3(0, 1, 0), 'map-sensor');
    // the crankcase vent hose from the cam cover, and the brake booster's vacuum hose leaving at the back
    {
      const bk = banks[0];
      const cv = W(bk, bk.sIn * (headHalf * 0.55), (bk.coverTop ?? headTop) + 0.06 * B, bk.z0);
      const pv = plen.position.clone().add(new V3(0, ph / 2, -(z1 - z0) * 0.3));
      sensor(g, pv, new V3(0, 1, 0), 'pcv', {}, 0.7);
      hose(g, [cv, cv.clone().add(new V3(0, 0.35 * B, 0)), cv.clone().lerp(pv, 0.5).add(new V3(0, 0.55 * B, 0)), pv.clone().add(new V3(0, 0.3 * B, 0)), pv.clone().add(new V3(0, 0.1 * B, 0))], 0.06 * B, 'pcv');
      const bv0 = a.clone().add(new V3(0, 0, -0.05 * B));
      hose(g, [bv0, bv0.clone().add(new V3(0, 0, -0.4 * B)), bv0.clone().add(new V3(0, 0.3 * B, -1.0 * B)), bv0.clone().add(new V3(0, 0.35 * B, -1.6 * B))], 0.08 * B, 'booster-hose');
    }
    const tb = part(new THREE.Group(), 'throttle');
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.3 * B, 0.3 * B, 0.45 * B, 24, 1, true), std('#b9bec5', 0.7, 0.4, {side: THREE.DoubleSide}));
    body.rotation.x = Math.PI / 2;
    const plate = new THREE.Mesh(new THREE.CylinderGeometry(0.28 * B, 0.28 * B, 0.015 * B, 24), M.steel);
    plate.rotation.z = 0.35;
    tb.add(body, plate);
    tb.position.copy(b).add(new V3(0, 0, 0.3 * B));
    // its flange to the plenum, four bolts, and the position sensor's connector on the shaft end
    const tfl = new THREE.Mesh(roundedBox(0.78 * B, 0.78 * B, 0.07 * B, 0.08 * B), std('#b9bec5', 0.7, 0.4));
    tfl.position.z = -0.2 * B;
    tb.add(tfl);
    bolts(tb, [[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([x, y]) => [new V3(x * 0.3 * B, y * 0.3 * B, -0.16 * B), new V3(0, 0, 1)]));
    sensor(tb, new V3(-0.32 * B, 0, 0), new V3(-1, 0, 0), 'throttle', {}, 0.8);
    g.add(tb);
    throttle = tb.position.clone();
    // the electronic throttle's motor housing beside the bore
    const act = part(new THREE.Mesh(bevBox(0.3 * B, 0.5 * B, 0.3 * B), M.black), 'throttle');
    act.position.set(0.42 * B, 0, 0);
    tb.add(act);
    if (!hw.turbo) {
      // the duct turns away from the engine (up off a V's valley, outboard on an inline) so it clears the front
      const away = multi ? new V3(0, 1, 0) : new V3(Math.sign(throttle.x) || 1, 0, 0);
      const t0 = throttle.clone().add(new V3(0, 0, 0.22 * B));
      const t1 = throttle.clone().add(new V3(0, 0, 0.75 * B)).addScaledVector(away, 0.15 * B);
      const t2 = throttle.clone().add(new V3(0, 0, 1.0 * B)).addScaledVector(away, 0.8 * B);
      hose(g, [t0, t1, t2], 0.26 * B, 'air-filter', {}, M.rubber);
      sensor(g, t1.clone().add(new V3(0, 0.26 * B, 0)), new V3(0, 1, 0), 'maf');
      const box = part(new THREE.Group(), 'air-filter');
      const shellBox = std('#1d2023', 0.05, 0.6);
      const lower = new THREE.Mesh(roundedBox(1.25 * B, 0.36 * B, 0.95 * B, 0.12 * B), shellBox);
      lower.position.y = -0.17 * B;
      const lid = new THREE.Mesh(roundedBox(1.27 * B, 0.3 * B, 0.97 * B, 0.12 * B), shellBox);
      lid.position.y = 0.17 * B;
      const seam = new THREE.Mesh(roundedBox(1.31 * B, 0.04 * B, 1.01 * B, 0.02 * B), plastic);
      box.add(lower, lid, seam);
      for (const [x, z] of [[-0.66, 0], [0.66, 0], [0, -0.51], [0, 0.51]]) {
        const clip = new THREE.Mesh(roundedBox(x ? 0.04 * B : 0.16 * B, 0.16 * B, x ? 0.16 * B : 0.04 * B, 0.015 * B), M.steel);
        clip.position.set(x * B, 0, z * B);
        box.add(clip);
      }
      box.position.copy(t2).addScaledVector(away, 0.3 * B).add(new V3(0, 0, 0.35 * B));
      g.add(box);
    }
    // port fuel injection with a rail (petrol); diesels inject in the head
    if (!hw.diesel) {
      const ig = worldGroup('ignition', exV);
      for (const bk of banks) {
        const ps = allPorts.filter((p) => p.bk === bk);
        const tops = [];
        for (const p of ps) {
          const up = new V3(0, 0, 1).cross(p.n).normalize();
          if (up.y < 0) up.negate();
          const inj = part(new THREE.Mesh(rod01(0.05 * B, 12), M.black), 'injector', {cyl: p.c.n});
          const t0 = p.injAt.clone().addScaledVector(up, 0.12 * B);
          const t1 = t0.clone().addScaledVector(up, 0.35 * B);
          along(inj, t0, t1);
          ig.add(inj);
          // the fuel spray: a cone from the tip toward the intake valve, while that cylinder draws in its charge
          const smat = new THREE.MeshBasicMaterial({color: '#cfe0ff', transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide});
          const sp = part(new THREE.Mesh(new THREE.ConeGeometry(0.09 * B, 0.4 * B, 16, 1, true).translate(0, -0.2 * B, 0), smat), 'spray', {cyl: p.c.n});
          sp.position.copy(t0);
          sp.quaternion.setFromUnitVectors(new V3(0, 1, 0), up);
          ig.add(sp);
          portSprays.push({c: p.c, mat: smat});
          tops.push(t1);
          for (const u of [0.04, 0.31]) {
            const o = part(new THREE.Mesh(new THREE.TorusGeometry(0.055 * B, 0.014 * B, 6, 20), M.rubber), 'injector', {cyl: p.c.n});
            o.position.copy(t0).addScaledVector(up, u * B);
            o.quaternion.setFromUnitVectors(new V3(0, 0, 1), up);
            ig.add(o);
          }
          const con = part(new THREE.Mesh(roundedBox(0.16 * B, 0.1 * B, 0.12 * B, 0.02 * B), plastic), 'injector', {cyl: p.c.n});
          con.position.copy(t0).addScaledVector(up, 0.2 * B).addScaledVector(p.n, 0.1 * B);
          ig.add(con);
          p.conAt = con.position.clone().addScaledVector(p.n, 0.1 * B);
        }
        // the injector loom: one lead from each connector into a sub-harness along the rail
        const cons = ps.map((p) => p.conAt).sort((u, v) => u.z - v.z);
        const loomPts = [cons[0].clone().add(new V3(0, 0, -0.5 * B)), ...cons, cons[cons.length - 1].clone().add(new V3(0, 0.2 * B, 0.6 * B))];
        ig.add(part(new THREE.Mesh(tube(loomPts, 0.045 * B, false, 30 * loomPts.length), wire), 'harness'));
        tops.sort((u, v) => u.z - v.z);
        const r0 = tops[0].clone().add(new V3(0, 0, -0.3 * B));
        const r1 = tops[tops.length - 1].clone().add(new V3(0, 0, 0.4 * B));
        const rail = part(new THREE.Mesh(rod01(0.07 * B, 12), M.steel), 'rail');
        along(rail, r0, r1);
        ig.add(rail);
        // the pressure damper on the rail's end and the steel feed line coming in from the back
        const damp = part(new THREE.Mesh(new THREE.CylinderGeometry(0.1 * B, 0.1 * B, 0.18 * B, 20).rotateX(Math.PI / 2), M.aluMachined), 'rail');
        damp.position.copy(r1);
        ig.add(damp);
        hose(ig, [r0, r0.clone().add(new V3(0, 0, -0.35 * B)), r0.clone().add(new V3(0, -0.25 * B, -0.9 * B)), r0.clone().add(new V3(0, -0.3 * B, -1.5 * B))], 0.035 * B, 'fuel-line', {}, braid, false);
        bolts(ig, [[r0.clone().add(new V3(0, 0.08 * B, 0.3 * B)), new V3(0, 1, 0)], [r1.clone().add(new V3(0, 0.08 * B, -0.35 * B)), new V3(0, 1, 0)]]);
      }
    }
  }

  // ------------------------------------------------------------ exhaust, and the turbo when fitted
  // hot metal glows as a black body. The solver gives the cylinder gas at exhaust-valve opening; the port sees that
  // gas after it blows down to the exhaust pressure, estimated here as an isentropic expansion with the solver's
  // mean gamma. The wall is taken 150 K below the port gas, and the turbine 50 K below that (assumptions).
  {
    const g = E.out.mean_gamma || 1.3;
    const pEVO = E.gas(E.EX[0]).p;
    const Tport = (E.out.exhaust_temperature_K || 900) * Math.pow(Math.min(1, E.pEx / pEVO), (g - 1) / g);
    E.portTemp = Tport;
    const Tw = Tport - 150;
    // the headers are drawn as bare stainless steel with no glow (a look choice); the wall temperature still sets the
    // heat tint of their service state below
    M.header.emissive.set('#000000');
    M.header.emissiveIntensity = 0;
    E.wallTemp = Tw;
    // service-state inputs: headers and turbine tint by their wall temperature; the exhaust valves carry carbon
    M.header.userData.T = Tw;
    M.turbine.userData.T = Tw - 50;
    M.turbine.userData.wearRole = 'hot';
    M.vex.userData.wearRole = 'carbon';
    M.cover.userData.wearRole = 'paint';
    const Tt = Tw - 50;
    blackbody(Tt, M.turbine.emissive);
    M.turbine.emissiveIntensity = Math.min(0.35, 0.3 * glowIntensity(Tt, 1200));
  }
  const collectors = [];
  // a catalytic converter: a fat stainless can on the pipe between two cones
  const catMat = std('#8e9297', 0.85, 0.5);
  const shieldMat = std('#a7abb0', 0.85, 0.35);
  const catalyst = (a, b) => {
    const L = Math.max(0.5 * B, a.distanceTo(b) - 0.3 * B);
    const m = part(new THREE.Group(), 'catalyst');
    m.add(new THREE.Mesh(new THREE.CapsuleGeometry(0.3 * B, L, 6, 24), catMat));
    // a ribbed heat shield wrapped over the top half, and a bolted flange at each end
    const sh = new THREE.Mesh(new THREE.CylinderGeometry(0.36 * B, 0.36 * B, L * 0.9, 32, 1, true, -Math.PI / 2, Math.PI), shieldMat);
    sh.material.side = THREE.DoubleSide;
    m.add(sh);
    for (let i = -2; i <= 2; i++) {
      const rib = new THREE.Mesh(new THREE.TorusGeometry(0.365 * B, 0.012 * B, 6, 24, Math.PI).rotateX(Math.PI / 2).rotateY(Math.PI), shieldMat);
      rib.position.y = (i * L * 0.85) / 5;
      m.add(rib);
    }
    for (const s of [-1, 1]) {
      const fl = new THREE.Mesh(new THREE.CylinderGeometry(0.3 * B, 0.3 * B, 0.05 * B, 24), M.forged);
      fl.position.y = s * (L / 2 + 0.32 * B);
      m.add(fl);
    }
    m.position.copy(a).lerp(b, 0.5);
    m.quaternion.setFromUnitVectors(new V3(0, 1, 0), new V3().subVectors(b, a).normalize());
    return m;
  };
  const vBand = (g, at, dir, r) => {
    const q = new THREE.Quaternion().setFromUnitVectors(new V3(0, 0, 1), dir.clone().normalize());
    const band = part(new THREE.Mesh(new THREE.TorusGeometry(r * 1.12, r * 0.14, 8, 32), M.steel), 'collector');
    band.position.copy(at);
    band.quaternion.copy(q);
    const nut = part(new THREE.Mesh(roundedBox(r * 0.5, r * 0.35, r * 0.35, r * 0.06), M.steel), 'collector');
    nut.position.copy(at).add(new V3(0, r * 1.3, 0).applyQuaternion(q));
    nut.quaternion.copy(q);
    g.add(band, nut);
  };
  for (const bk of banks) {
    const n = new V3(bk.p[0], bk.p[1], 0).multiplyScalar(bk.sEx);
    const g = worldGroup('exhaust', n.clone().multiplyScalar(1.8 * B));
    const flat = Math.abs(bk.b[0]) > 0.9;
    const colB = flat ? E.deck - 0.3 * B : E.deck - 1.3 * B;
    const colP = bk.sEx * (headHalf + 0.75 * B);
    for (const p of ports(bk, bk.sEx)) {
      const pts = [p.inside, p.exit, W(bk, bk.sEx * (headHalf + 0.45 * B), E.deck + 0.15 * B, p.c.z), W(bk, colP, (E.deck + colB) / 2 + 0.1 * B, p.c.z - 0.15 * B), W(bk, colP, colB, p.c.z - 0.35 * B)];
      g.add(part(new THREE.Mesh(ctube(pts, 0.15 * B), M.header), 'header', {cyl: p.c.n}));
      const tEnd = new V3().subVectors(pts[4], pts[3]).normalize();
      const collar = part(new THREE.Mesh(new THREE.CylinderGeometry(0.175 * B, 0.175 * B, 0.12 * B, 24), M.header), 'header', {cyl: p.c.n});
      collar.position.copy(pts[3]).lerp(pts[4], 0.75);
      collar.quaternion.setFromUnitVectors(new V3(0, 1, 0), tEnd);
      g.add(collar);
      // the flange each pipe is bolted to the head with: two studs either side of the port
      const nrm = new V3().subVectors(p.exit, p.inside).normalize();
      const fl = part(new THREE.Mesh(bevBox(0.62 * B, 0.42 * B, 0.06 * B), M.forged), 'header', {cyl: p.c.n});
      fl.position.copy(p.exit);
      fl.quaternion.setFromUnitVectors(new V3(0, 0, 1), nrm);
      g.add(fl);
      bolts(g, [-1, 1].map((s) => [p.exit.clone().add(new V3(0, 0, s * 0.23 * B)).addScaledVector(nrm, 0.03 * B), nrm]));
    }
    // a lambda sensor screwed into each collector, reading the exhaust's oxygen
    {
      const at = W(bk, colP, colB, (bk.z1 + 0.2 * B + zRear - 0.5 * B) / 2);
      const o2 = part(new THREE.Group(), 'o2-sensor', {bank: bk.id});
      const hex = new THREE.Mesh(new THREE.CylinderGeometry(0.07 * B, 0.07 * B, 0.07 * B, 6), M.steel);
      const body = new THREE.Mesh(new THREE.CylinderGeometry(0.045 * B, 0.045 * B, 0.2 * B, 12), M.black);
      body.position.y = 0.12 * B;
      o2.add(hex, body);
      o2.position.copy(at).addScaledVector(n, 0.25 * B);
      o2.quaternion.setFromUnitVectors(new V3(0, 1, 0), n);
      g.add(o2);
    }
    const za = bk.z1 + 0.2 * B;
    const zb = zRear - 0.5 * B;
    const col = part(new THREE.Mesh(ctube([W(bk, colP, colB, za), W(bk, colP, colB, (za + zb) / 2), W(bk, colP, colB, zb)], 0.24 * B), M.header), 'collector', {bank: bk.id});
    g.add(col);
    collectors.push({bk, end: W(bk, colP, colB, zb), g});
    vBand(g, W(bk, colP, colB, zb + 0.15 * B), new V3(0, 0, 1), 0.24 * B);
  }
  if (hw.turbo) {
    const g = worldGroup('exhaust', new V3(0, 0, -1.6 * B));
    const c0 = collectors[0];
    const tc = c0.end.clone().add(new V3(0, 0, -0.7 * B));
    const turbo = part(new THREE.Group(), 'turbo');
    turbo.position.copy(tc);
    const tHouse = new THREE.Mesh(new THREE.TorusGeometry(0.42 * B, 0.2 * B, 14, 40), M.turbine);
    const cHouse = new THREE.Mesh(new THREE.TorusGeometry(0.46 * B, 0.18 * B, 14, 40), M.compressor);
    cHouse.position.x = 0.75 * B;
    const core = new THREE.Mesh(new THREE.CylinderGeometry(0.2 * B, 0.2 * B, 0.6 * B, 20), M.forged);
    core.rotation.z = Math.PI / 2;
    core.position.x = 0.38 * B;
    tHouse.rotation.y = cHouse.rotation.y = Math.PI / 2;
    const wheel = (x) => {
      const w = new THREE.Group();
      for (let i = 0; i < 9; i++) {
        const blade = new THREE.Mesh(bevBox(0.02 * B, 0.25 * B, 0.12 * B), M.steel);
        blade.position.y = 0.13 * B;
        const h = new THREE.Group();
        h.rotation.x = (i / 9) * Math.PI * 2;
        h.add(blade);
        w.add(h);
      }
      w.position.x = x;
      return w;
    };
    const tw = wheel(0);
    const cw = wheel(0.75 * B);
    turbo.add(tHouse, cHouse, core, tw, cw);
    g.add(turbo);
    // the bearing housing's oil: a braided feed from the block above, a fat drain back to the sump below
    {
      const core = tc.clone().add(new V3(0.38 * B, 0, 0));
      const src = W(banks[0], banks[0].sEx * 0.6 * B, E.deck - 0.5 * B, banks[0].z0);
      hose(g, [src, src.clone().add(new V3(0, 0.3 * B, -0.2 * B)), core.clone().add(new V3(0, 0.6 * B, 0.2 * B)), core.clone().add(new V3(0, 0.22 * B, 0))], 0.03 * B, 'turbo-oil', {}, braid, false);
      hose(g, [core.clone().add(new V3(0, -0.22 * B, 0)), core.clone().add(new V3(0, -0.7 * B, 0.2 * B)), new V3(core.x * 0.7, -caseR + 0.1 * B, core.z + 0.6 * B)], 0.07 * B, 'turbo-oil');
    }
    // the shaft speed is not modelled; the wheels turn only so the part reads as rotating
    movers.push((th) => (tw.rotation.x = cw.rotation.x = th * 6 * D2R));
    for (const c of collectors.slice(1)) g.add(part(new THREE.Mesh(ctube([c.end, c.end.clone().add(new V3(0, -0.8 * B, -0.4 * B)), tc.clone().add(new V3(0, -0.6 * B, 0))], 0.2 * B), M.header), 'collector'));
    g.add(part(new THREE.Mesh(ctube([c0.end, tc], 0.22 * B), M.header), 'collector'));
    g.add(part(new THREE.Mesh(ctube([tc.clone().add(new V3(-0.2 * B, -0.3 * B, 0)), tc.clone().add(new V3(-0.3 * B, -1.2 * B, -0.4 * B)), tc.clone().add(new V3(-0.3 * B, -1.5 * B, -1.4 * B))], 0.22 * B), M.header), 'downpipe'));
    g.add(catalyst(tc.clone().add(new V3(-0.3 * B, -1.25 * B, -0.5 * B)), tc.clone().add(new V3(-0.3 * B, -1.5 * B, -1.4 * B))));
    if (throttle) {
      const out = tc.clone().add(new V3(0.75 * B, 0.5 * B, 0));
      const hi = new V3(out.x, Math.max(out.y, throttle.y) + 0.4 * B, out.z);
      g.add(part(new THREE.Mesh(tube([out, hi, new V3(hi.x, hi.y, zMid), new V3(throttle.x, throttle.y + 0.2 * B, throttle.z + 0.9 * B), throttle.clone().add(new V3(0, 0, 0.3 * B))], 0.16 * B, false, 96), std('#9aa3ad', 0.7, 0.35)), 'charge-pipe'));
    }
  } else {
    for (const c of collectors) {
      const g = worldGroup('exhaust', new V3(0, 0, -1.2 * B));
      g.add(part(new THREE.Mesh(ctube([c.end, c.end.clone().add(new V3(0, -0.6 * B, -0.6 * B)), c.end.clone().add(new V3(0, -0.9 * B, -1.6 * B))], 0.22 * B), M.header), 'downpipe'));
      g.add(catalyst(c.end.clone().add(new V3(0, -0.65 * B, -0.75 * B)), c.end.clone().add(new V3(0, -0.9 * B, -1.6 * B))));
    }
  }

  // ------------------------------------------------------------ ignition: plugs and coils, or diesel injectors
  for (const bk of banks) {
    const g = bankGroup('ignition', bk, 3.2 * B);
    // what burns stays in the cylinder: the spark, the flame front and the sprays sit in a group that does not move
    // when the engine explodes, while the plugs, coils and injectors lift away with the rest of the ignition layer
    const gc = bankGroup('ignition', bk, 0);
    const coilsAt = [];
    for (const c of bk.cs) {
      const k = C.find((x) => x.c === c);
      // the spark (or the injector spray) is a point of light just inside the chamber
      // HDR colour above 1, so the bloom pass picks the spark out
      const pm = new THREE.MeshBasicMaterial({color: hw.diesel ? new THREE.Color(4, 2.6, 1.2) : new THREE.Color(2.6, 3.4, 4.5), transparent: true, opacity: 0, depthWrite: false});
      k.plugMat = pm;
      // a central plug between overhead cams; offset and tilted beside one cam or a rocker shaft
      const tilt = hw.valvetrain === 'dohc' ? 0 : bk.sEx * 18 * D2R;
      const p0 = hw.valvetrain === 'dohc' ? 0 : hw.diesel ? bk.sIn * 0.3 * B : bk.sEx * 0.3 * B;
      const u = [Math.sin(hw.diesel ? -tilt : tilt), Math.cos(tilt)];
      const len = bk.coverTop - E.deck + 0.05 * B;
      const plug = part(new THREE.Group(), hw.diesel ? 'diesel-injector' : 'plug', {cyl: c.n});
      plug.rotation.z = -Math.atan2(u[0], u[1]);
      if (hw.diesel) {
        const body = new THREE.Mesh(rod01(0.07 * B, 16), M.steel);
        body.scale.y = len;
        const nozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.03 * B, 0.045 * B, 0.12 * B, 12), M.pin);
        nozzle.position.y = -0.04 * B;
        const nut = new THREE.Mesh(new THREE.CylinderGeometry(0.1 * B, 0.1 * B, 0.1 * B, 6), M.bolt);
        nut.position.y = len * 0.6;
        plug.add(body, nozzle, nut);
        plug.position.set(p0, E.deck, c.z);
      } else {
        const pg = plugGeometries(B);
        plug.add(new THREE.Mesh(pg.thread, M.steel), new THREE.Mesh(pg.hex, M.steel), new THREE.Mesh(pg.ins, M.ceramic), new THREE.Mesh(pg.term, M.steel));
        // seated on the head with its thread reaching down to the chamber
        const thr = 0.019 * (B / 0.086);
        plug.position.set(p0 + u[0] * thr, E.deck + u[1] * thr, c.z);
      }
      g.add(plug);
      const spark = new THREE.Mesh(new THREE.SphereGeometry(0.07 * B, 12, 8), pm);
      spark.userData.spark = true;
      spark.position.set(p0, E.deck - 0.03 * B, c.z);
      gc.add(spark);
      // The flame front: a hemisphere growing down from the plug (or, in a diesel, from the injector) whose volume is
      // the burned gas's share of the cylinder at this crank angle. Burned gas is about four times less dense than
      // the unburned charge, so a mass fraction burned xb fills a volume fraction 4xb / (1 + 3xb).
      const fmat = new THREE.MeshBasicMaterial({color: '#ff9a3c', transparent: true, opacity: 0.55, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide});
      const front = part(new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), fmat), 'flame-front', {cyl: c.n});
      front.userData.spark = true;
      front.position.copy(spark.position);
      front.visible = false;
      // built at unit radius and scaled each frame; kept tiny when idle so the engine's bounds (which count hidden
      // objects) are not sized around a one-metre sphere
      front.scale.setScalar(1e-4);
      gc.add(front);
      k.front = front;
      k.fmat = fmat;
      // a diesel's six injection plumes, fanning down and out from the nozzle into the bowl
      if (hw.diesel) {
        const sg = new THREE.Group();
        const cone = new THREE.ConeGeometry(0.04 * B, 0.3 * B, 10, 1, true).translate(0, -0.15 * B, 0);
        const smat = new THREE.MeshBasicMaterial({color: '#cfe0ff', transparent: true, opacity: 0.0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide});
        for (let j = 0; j < 6; j++) {
          const m = new THREE.Mesh(cone, smat);
          m.rotation.set(0, (j / 6) * Math.PI * 2, 0);
          m.rotateZ(1.15);
          sg.add(m);
        }
        sg.position.copy(spark.position);
        gc.add(part(sg, 'spray', {cyl: c.n}));
        k.spray = smat;
      }
      if (!hw.diesel) {
        const coil = part(new THREE.Mesh(bevBox(0.42 * B, 0.18 * B, 0.3 * B), M.coil), 'coil', {cyl: c.n});
        coil.position.set(p0 + u[0] * len, E.deck + u[1] * len, c.z);
        coil.rotation.z = plug.rotation.z;
        const boot = new THREE.Mesh(rod01(0.07 * B, 12), M.black);
        boot.position.set(p0 + u[0] * 0.5 * B, E.deck + u[1] * 0.5 * B, c.z);
        boot.rotation.z = plug.rotation.z;
        boot.scale.y = len - 0.5 * B;
        const ear = new THREE.Mesh(roundedBox(0.16 * B, 0.04 * B, 0.13 * B, 0.015 * B), M.coil);
        ear.position.set(0.27 * B, -0.07 * B, 0);
        const cplug = new THREE.Mesh(roundedBox(0.14 * B, 0.09 * B, 0.12 * B, 0.02 * B), plastic);
        cplug.position.set(-0.12 * B, 0.12 * B, 0);
        coil.add(ear, cplug);
        bolts(coil, [[new V3(0.29 * B, -0.05 * B, 0), new V3(0, 1, 0)]]);
        g.add(coil, boot);
        coilsAt.push(coil.position.clone());
      }
    }
    // the loom that feeds every coil, with a plug-in connector at each
    if (coilsAt.length) {
      const off = new V3(bk.sIn * 0.34 * B, 0.08 * B, 0);
      const pts = coilsAt.map((q2) => q2.clone().add(off));
      pts.sort((u, v) => u.z - v.z);
      pts.unshift(pts[0].clone().add(new V3(0, 0, -0.4 * B)));
      pts.push(pts[pts.length - 1].clone().add(new V3(0, 0.15 * B, 0.7 * B)));
      g.add(part(new THREE.Mesh(tube(pts, 0.05 * B, false, 24 * pts.length), M.rubber), 'harness'));
      for (const q2 of coilsAt) {
        const con = part(new THREE.Mesh(bevBox(0.2 * B, 0.1 * B, 0.13 * B), M.black), 'harness');
        con.position.copy(q2).add(new V3(bk.sIn * 0.2 * B, 0.07 * B, 0));
        g.add(con);
      }
    }
  }

  // ------------------------------------------------------------ outside hardware: bellhousing, starter, mounts, coolant
  const flat = banks.some((bk) => Math.abs(bk.b[0]) > 0.9);
  {
    // the bellhousing round the flywheel, flared and ribbed, with its flange bolts
    const g = worldGroup('block', new V3(0, 0, -1.8 * B));
    const Rf = Math.max(caseR, 1.2 * B) + 0.06 * B;
    // a flange, a near-parallel skirt over the flywheel and clutch, then a shoulder down to the gearbox case
    const prof = [[Rf + 0.08 * B, 0.02 * B], [Rf + 0.08 * B, -0.1 * B], [Rf - 0.02 * B, -0.14 * B], [Rf - 0.1 * B, -0.85 * B], [Rf * 0.72, -1.05 * B], [Rf * 0.62, -1.1 * B], [Rf * 0.6, -1.5 * B]];
    const bell = new THREE.LatheGeometry(prof.map(([r, h]) => new THREE.Vector2(r, h)), 48).rotateX(Math.PI / 2).translate(0, 0, zRear);
    const bm = shellMat('#a4a7ab');
    boxWithEdges(g, bell, bm, new V3(), 'bellhousing');
    const fb = [];
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2;
      fb.push([new V3((Rf + 0.02 * B) * Math.cos(a), (Rf + 0.02 * B) * Math.sin(a), zRear - 0.1 * B), new V3(0, 0, -1)]);
    }
    bolts(g, fb);
    // the starter on the bell flange, its pinion reaching in to the ring gear
    if (!flat) {
      const sg = worldGroup('accessory', new V3(-1.4 * B, 0, 0));
      const st = part(new THREE.Group(), 'starter');
      const motor = new THREE.Mesh(new THREE.CylinderGeometry(0.3 * B, 0.3 * B, 0.85 * B, 28).rotateX(Math.PI / 2), M.alu);
      motor.position.z = 0.45 * B;
      const endCap = new THREE.Mesh(new THREE.CylinderGeometry(0.31 * B, 0.27 * B, 0.12 * B, 28).rotateX(Math.PI / 2), M.black);
      endCap.position.z = 0.92 * B;
      const sol = new THREE.Mesh(new THREE.CylinderGeometry(0.14 * B, 0.14 * B, 0.6 * B, 20).rotateX(Math.PI / 2), M.aluMachined);
      sol.position.set(0, 0.38 * B, 0.35 * B);
      const nose = new THREE.Mesh(new THREE.CylinderGeometry(0.2 * B, 0.24 * B, 0.2 * B, 24).rotateX(Math.PI / 2), M.alu);
      nose.position.z = -0.08 * B;
      st.add(motor, endCap, sol, nose);
      st.position.set(-(caseR + 0.36 * B), -0.5 * B, zRear);
      sg.add(st);
    }
    // engine mounts either side of the crankcase: a bracket, a rubber bush, a plate for the chassis
    if (!flat) for (const sx of [-1, 1]) {
      const mg = worldGroup('block', new V3(sx * 1.2 * B, 0, 0));
      const mt = part(new THREE.Group(), 'mount');
      const br = new THREE.Mesh(roundedBox(0.34 * B, 0.5 * B, 0.6 * B, 0.08 * B), M.castShell('#4a4f56'));
      br.position.x = sx * 0.17 * B;
      const bush = new THREE.Mesh(new THREE.CylinderGeometry(0.24 * B, 0.24 * B, 0.3 * B, 24).rotateZ(Math.PI / 2), M.rubber);
      bush.position.x = sx * 0.49 * B;
      const plate = new THREE.Mesh(roundedBox(0.08 * B, 0.7 * B, 0.7 * B, 0.03 * B), M.forged);
      plate.position.x = sx * 0.68 * B;
      mt.add(br, bush, plate);
      mt.position.set(sx * caseR, 0.1 * B, zMid + 0.2 * B);
      mg.add(mt);
      bolts(mg, [-1, 1].map((s) => [new V3(sx * (caseR + 0.72 * B), 0.1 * B + s * 0.22 * B, zMid + 0.2 * B), new V3(sx, 0, 0)]));
    }
  }
  {
    // coolant leaves through the thermostat above the water pump and goes forward to the radiator
    const g = worldGroup('accessory', new V3(0, 0, 2.6 * B));
    const topY = Math.max(...banks.map((bk) => W(bk, 0, E.deck).y));
    const wy = Math.max(1.5 * B, 0.55 * topY);
    const zA = zFront + 0.62 * B;
    const thermo = part(new THREE.Group(), 'thermostat');
    const house = new THREE.Mesh(new THREE.CylinderGeometry(0.17 * B, 0.2 * B, 0.3 * B, 20), M.alu);
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.11 * B, 0.11 * B, 0.3 * B, 16).rotateX(Math.PI / 2), M.alu);
    neck.position.set(0, 0.05 * B, 0.2 * B);
    thermo.add(house, neck);
    thermo.position.set(0.55 * B, wy + 0.35 * B, zA - 0.45 * B);
    g.add(thermo);
    const h0 = thermo.position.clone().add(new V3(0, 0.05 * B, 0.35 * B));
    hose(g, [h0, h0.clone().add(new V3(0.1 * B, 0.15 * B, 0.5 * B)), h0.clone().add(new V3(0.3 * B, 0.1 * B, 1.1 * B))], 0.1 * B, 'thermostat');
    sensor(g, thermo.position.clone().add(new V3(0.17 * B, 0.05 * B, 0)), new V3(1, 0.3, 0), 'coolant-sensor', {}, 0.8);
    // the lower hose back from the radiator into the pump
    const lp = new V3(-0.36 * B, wy - 0.1 * B, zA - 0.3 * B);
    hose(g, [lp, lp.clone().add(new V3(-0.25 * B, -0.1 * B, 0)), lp.clone().add(new V3(-0.45 * B, -0.5 * B, 0.6 * B)), lp.clone().add(new V3(-0.5 * B, -0.8 * B, 1.1 * B))], 0.1 * B, 'thermostat');
  }
  {
    // two heater hoses off the back of the first head, on their way to the cabin heater core
    const g = worldGroup('accessory', new V3(0, 0.8 * B, -0.8 * B));
    const bk = banks[0];
    for (const [k, dp] of [[0, 0.25], [1, 0.6]]) {
      const s0 = W(bk, bk.sIn * dp * B * (multi ? -1 : 1), headTop - 0.15 * B, bk.z0 - 0.7 * B);
      hose(g, [s0, s0.clone().add(new V3(0, 0, -0.3 * B)), s0.clone().add(new V3(0, 0.25 * B + k * 0.1 * B, -1.0 * B)), s0.clone().add(new V3(0, 0.3 * B + k * 0.1 * B, -1.6 * B))], 0.07 * B, 'heater-hose');
    }
  }
  {
    // the main engine harness: a corrugated trunk along the intake side, clipped to the block, from the front
    // sensors back to where it leaves for the engine computer
    const bk = banks[0];
    const g = bankGroup('ignition', bk, 2.0 * B);
    const hx = bk.sIn * (multi ? -0.7 : 0.78) * B;
    const hy = flat ? E.deck - 0.1 * B : bBot + 0.35 * B;
    const pts = [new V3(hx, hy + 0.2 * B, bk.z1 + 1.0 * B), new V3(hx, hy, bk.z1 + 0.4 * B), new V3(hx, hy, (bk.z0 + bk.z1) / 2), new V3(hx, hy, bk.z0 - 0.4 * B), new V3(hx * 1.3, hy + 0.3 * B, bk.z0 - 1.2 * B), new V3(hx * 1.5, hy + 0.5 * B, bk.z0 - 1.8 * B)];
    g.add(part(new THREE.Mesh(tube(pts, 0.07 * B, false, 160), wire), 'harness'));
    const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
    for (let i = 1; i < 10; i++) {
      const u = i / 10;
      const clip = part(new THREE.Mesh(roundedBox(0.1 * B, 0.18 * B, 0.08 * B, 0.02 * B), plastic), 'harness');
      clip.position.copy(curve.getPointAt(u));
      clip.quaternion.setFromUnitVectors(new V3(0, 0, 1), curve.getTangentAt(u));
      g.add(clip);
    }
  }

  // ------------------------------------------------------------ pose
  const tmp = new THREE.Color();
  const sparkAt = mod((E.input.combustion_start_deg ?? -15) + 720, 720);
  /** pose for crank angle th (degrees). opts: track (cylinder number), cut ('glass' | 'section' | 'solid') */
  const update = (th, opts = {}) => {
    for (const f of movers) f(th);
    // port injection while each cylinder is on its intake stroke
    for (const s of portSprays) {
      const ps = E.psi(s.c, th);
      s.mat.opacity = chargeOf(ps, E.gas(ps).xb) === 0 ? 0.35 : 0;
    }
    flowTex.offset.x = -mod(th / 360, 1);
    for (const k of C) {
      const {c} = k;
      const {s, P} = E.pistonS(c, th);
      const Wp = [s * c.b[0], s * c.b[1]];
      k.piston.position.set(Wp[0] + E.crownH * c.b[0], Wp[1] + E.crownH * c.b[1], c.z);
      k.rod.position.set(P[0], P[1], c.z);
      k.rod.rotation.z = -Math.atan2(Wp[0] - P[0], Wp[1] - P[1]);
      const crown = s + E.crownH;
      k.charge.position.set(crown * c.b[0], crown * c.b[1], c.z);
      k.charge.scale.set(1, Math.max(1e-4, E.deck - crown), 1);
      const ps = E.psi(c, th);
      const g = E.gas(ps);
      const key = chargeOf(ps, g.xb);
      tmp.copy(CHARGE[key]);
      if (key === 2) tmp.lerp(CHARGE[3], Math.min(1, Math.max(0, (ps < 540 ? ps : 0) - 40) / 140));
      k.cm.color.copy(tmp);
      // the burning charge glows as a black body at the solver's gas temperature: colour from the Planck locus,
      // brightness rising as T^4 above the Draper point
      const glow = key === 2 ? glowIntensity(g.T, 2400) : 0;
      if (glow > 0) blackbody(g.T, k.cm.emissive);
      k.cm.emissiveIntensity = Math.min(3.2, 1.2 * glow);
      const tw = k.charge.userData.glowTwin;
      if (tw) {
        tw.visible = glow > 0;
        tw.material.color.copy(k.cm.emissive).multiplyScalar(k.cm.emissiveIntensity);
      }
      const burning = Math.min(1, glow);
      k.cm.opacity = key === 2 ? 0.45 + 0.35 * burning : key === 3 ? 0.35 : 0.42;
      const dS = mod(ps - sparkAt, 720);
      if (k.plugMat) k.plugMat.opacity = dS < 14 ? 1 - dS / 14 : 0;
      if (k.front) {
        const xb = g.xb;
        const on = key === 2 && xb > 0.002 && xb < 0.995 && dS < 300;
        k.front.visible = on;
        if (!on) k.front.scale.setScalar(1e-4);
        if (on) {
          const vf = (4 * xb) / (1 + 3 * xb);
          const r = Math.min(0.62 * B, Math.cbrt((3 * vf * E.volume(c, th)) / (2 * Math.PI)));
          k.front.scale.set(r, r, r);
          blackbody(Math.max(1200, g.T), k.fmat.color);
          k.fmat.opacity = 0.55 * (1 - xb * 0.6);
        }
      }
      if (k.spray) k.spray.opacity = dS < 25 ? 0.5 * (1 - dS / 25) : 0;
      const tracked = c.n === opts.track;
      k.rimMat.color.set(tracked ? ACCENT : '#6c737c');
      k.rimMat.emissive.set(tracked ? ACCENT : '#000000');
      k.rimMat.emissiveIntensity = tracked ? 0.5 : 0;
    }
  };

  const setCut = (mode, z) => {
    CLIP.constant = z;
    // outlines help read the glass shells; on solid metal they turn the engine into a drawing
    edgeMat.visible = mode === 'glass';
    for (const o of shellMeshes) o.castShadow = mode !== 'glass';
    for (const m of shells) {
      const solid = mode !== 'glass';
      m.opacity = solid ? 1 : m === coverMat ? 0.18 : m.userData.glassOpacity ?? (m.userData.glassOpacity = m.opacity);
      m.transparent = !solid;
      m.depthWrite = solid;
    }
    const seen = new Set();
    root.traverse((o) => {
      for (const m of [].concat(o.material || [])) {
        if (seen.has(m)) continue;
        seen.add(m);
        if (m.userData.side === undefined) m.userData.side = m.side;
        m.clippingPlanes = mode === 'section' ? [CLIP] : null;
        m.side = mode === 'section' ? THREE.DoubleSide : m.userData.side;
        m.needsUpdate = true;
      }
    });
  };
  const setExplode = (e) => {
    for (const {g, v} of explodable) g.position.copy(v).multiplyScalar(e);
  };
  const setLayer = (id, on) => (layer[id].visible = on);

  // what emits light, for the glow pass: the charge, the spark, and exhaust metal hot enough to glow
  // Each glowing mesh gets an emission-only twin (same geometry, a child so it follows every move) that the glow
  // pass draws; the lit surface itself never feeds the bloom. Sparks are pure light already.
  const glowers = [];
  const hot = [];
  root.traverse((o) => {
    if (!o.isMesh) return;
    const m = o.material;
    if (o.userData.spark) glowers.push(o);
    else if (o.userData.pick?.id === 'charge' || ((m === M.header || m === M.turbine) && m.emissiveIntensity > 0.02)) hot.push(o);
  });
  for (const o of hot) {
    // the twin sits exactly on the surface the depth prepass already wrote, so without an offset the two fight
    // for the same depth and the glow flashes on and off from frame to frame
    const tm = new THREE.MeshBasicMaterial({
      color: new THREE.Color(o.material.emissive).multiplyScalar(o.material.emissiveIntensity),
      depthWrite: false,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -4,
      clippingPlanes: o.material.clippingPlanes,
    });
    const twin = new THREE.Mesh(o.geometry, tm);
    o.add(twin);
    glowers.push(twin);
    o.userData.glowTwin = twin;
  }

  root.traverse((o) => {
    if (!o.isMesh || o.userData.spark) return;
    const m = o.material;
    if (m.userData?.shell) {
      shellMeshes.push(o);
      o.receiveShadow = true;
    } else if (!m.transparent && !m.isMeshBasicMaterial) {
      o.receiveShadow = true;
      // only parts big enough to throw a visible shadow go into the shadow pass; a sensor or a clip would just
      // double the draw calls
      if (!o.geometry.boundingSphere) o.geometry.computeBoundingSphere();
      o.castShadow = o.isInstancedMesh || o.geometry.boundingSphere.radius * o.getWorldScale(new V3()).x > 0.25 * B;
    }
  });

  return {root, update, setCut, setExplode, setLayer, CLIP, zFront, zRear, glowers, layers: layer, info: {banks, cams, valves, throws, headHalf}};
}

// Lighting environments shared by the JetLab and PistonLab 3D viewers. Each is a small scene of emissive cards and
// surfaces rendered into a PMREM environment map, so its light sources carry real dynamic range (soft boxes and strip
// lights well above 1.0) and metal reflects long, clean highlights from them. The visible backdrop stays a dark
// gradient so the interface reads over it; each environment tints it to match.
//
// Light units: the environment's emitters are in relative radiance (the studio's key soft box is 5.5); the directional
// key light is in three's physically based units at exposure 1.3 under AgX. One exposure model for all four.
import * as THREE from 'three';

const card = (s, w, h, pos, I, color = '#ffffff', look = new THREE.Vector3()) => {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({color: new THREE.Color(color).multiplyScalar(I), side: THREE.DoubleSide}));
  m.position.copy(pos);
  m.lookAt(look);
  s.add(m);
  return m;
};
const dome = (s, color, r = 10) => s.add(new THREE.Mesh(new THREE.SphereGeometry(r, 48, 24), new THREE.MeshBasicMaterial({color, side: THREE.BackSide})));
const V = (x, y, z) => new THREE.Vector3(x, y, z);

export const ENVIRONMENTS = {
  studio: {
    name: 'Studio',
    // a photo studio: mid-grey cyclorama (enough bounce that recesses never go to pure black), a large overhead soft
    // box, two tall strip boxes behind either side, a warm fill card, a floor bounce
    build() {
      const s = new THREE.Scene();
      dome(s, '#1d1f23');
      card(s, 7, 4.5, V(0.5, 7.5, 1.2), 5.5);
      card(s, 1.3, 7.5, V(-6.8, 2.2, -2.4), 4.2, '#f2f5ff');
      card(s, 1.3, 7.5, V(6.8, 2.2, -2.8), 3.6, '#e6eeff');
      card(s, 5.5, 2.4, V(2.5, 1.2, 7.2), 1.2, '#fff3e4');
      card(s, 14, 14, V(0, -6, 0), 0.12, '#d8d4cc');
      return s;
    },
    bg: ['#131418', '#0d0e11', '#08090b'],
    sun: {color: '#fff8ee', intensity: 2.6},
    hemi: 0.3,
    rim: {color: '#cfdcf0', intensity: 1.3},
  },
  testcell: {
    name: 'Test cell',
    // an engine test cell: bare concrete walls and floor, rows of cool fluorescent strips along the ceiling, a dark
    // steel gantry band, the bright mouth of the inlet stack at one end
    build() {
      const s = new THREE.Scene();
      dome(s, '#3d3c3a');
      card(s, 30, 30, V(0, -5, 0), 0.32, '#8e8b85');
      for (const x of [-3.2, 0, 3.2]) for (const z of [-6, -2, 2, 6]) card(s, 0.25, 3.2, V(x, 7, z), 9, '#e8f0ff');
      card(s, 30, 1.2, V(0, 3.5, -9), 0.04, '#202224');
      card(s, 5, 5, V(0, 2.5, 9.5), 2.4, '#dfe6ee');
      return s;
    },
    bg: ['#1c1d1e', '#141516', '#0d0e0f'],
    sun: {color: '#eef3ff', intensity: 2.0},
    hemi: 0.45,
    rim: {color: '#d6e2f2', intensity: 1.0},
  },
  hangar: {
    name: 'Hangar',
    // a maintenance hangar: a grid of round high-bay lights, a light painted floor that bounces a lot, dark far walls,
    // and daylight through the open door on one side
    build() {
      const s = new THREE.Scene();
      dome(s, '#24272a');
      card(s, 30, 30, V(0, -5, 0), 0.55, '#a7b0a8');
      for (const x of [-5, -1.7, 1.7, 5]) for (const z of [-5, -1.7, 1.7, 5]) {
        const m = new THREE.Mesh(new THREE.CircleGeometry(0.45, 24), new THREE.MeshBasicMaterial({color: new THREE.Color('#fff4e2').multiplyScalar(14), side: THREE.DoubleSide}));
        m.position.set(x, 8, z);
        m.lookAt(0, 0, 0);
        s.add(m);
      }
      card(s, 12, 6, V(-9.5, 2, 0), 3.2, '#dfe8f5');
      return s;
    },
    bg: ['#1a1c1f', '#121416', '#0b0c0e'],
    sun: {color: '#fff2df', intensity: 2.2},
    hemi: 0.5,
    rim: {color: '#dce6f5', intensity: 1.1},
  },
  overcast: {
    name: 'Overcast',
    // outdoors under cloud: a bright sky dome brightest overhead, a grey horizon, dark tarmac; soft, shadowless light
    build() {
      const s = new THREE.Scene();
      const g = new THREE.SphereGeometry(10, 48, 24);
      const col = [];
      const c = new THREE.Color();
      const p = g.attributes.position;
      for (let i = 0; i < p.count; i++) {
        const y = p.getY(i) / 10;
        if (y >= 0) c.setRGB(1.0, 1.02, 1.06).multiplyScalar(1.1 + 1.4 * y);
        else c.set('#3b3c3c').multiplyScalar(0.6 + 0.4 * (1 + y));
        col.push(c.r, c.g, c.b);
      }
      g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
      s.add(new THREE.Mesh(g, new THREE.MeshBasicMaterial({vertexColors: true, side: THREE.BackSide})));
      return s;
    },
    bg: ['#2a2f36', '#1b1e22', '#101214'],
    sun: {color: '#f4f6fa', intensity: 0.9},
    hemi: 0.9,
    rim: {color: '#e4eaf2', intensity: 0.4},
  },
};

/** a vertical gradient for the backdrop */
export function backdrop([top, mid, bottom]) {
  const c = document.createElement('canvas');
  c.width = 4;
  c.height = 512;
  const g = c.getContext('2d');
  const gr = g.createLinearGradient(0, 0, 0, 512);
  gr.addColorStop(0, top);
  gr.addColorStop(0.6, mid);
  gr.addColorStop(1, bottom);
  g.fillStyle = gr;
  g.fillRect(0, 0, 4, 512);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

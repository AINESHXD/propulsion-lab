// Service state and wear, shared by the JetLab and PistonLab 3D viewers. One value, wear in [0, 1], moves every part
// from factory new to overhaul condition without touching geometry. The look is procedural and spatially plausible,
// never a noise overlay laid over everything:
//
//   every part      per-instance variation (blades in a row differ a little in tint, sheen and damage), a light dust
//   low surfaces    an oil film that collects toward the bottom of the engine: darker and glossier
//   hot metal       soot in the hottest zones, and a heat tint (a thin oxide film, as iridescence) whose colour follows
//                   the part's temperature from the cycle solve and whose strength grows with time in service
//   coated airfoils thermal-barrier coating fades, then spalls to the darker bond coat beneath
//   leading edges   erosion on compressor and fan blades: a dulled, roughened band along the leading edge
//   paint           chalks and chips to bare metal
//   cast iron       rust bloom in the low, wet places
//   pistons, valves carbon deposits
//
// Each material gets a role (from its alloy, or set by the engine) and, if hot, a temperature in kelvin in
// material.userData.T. applyWear() installs the shader code once per material; setWear() just moves a uniform.
import * as THREE from 'three';

export const STATES = [
  {id: 'new', name: 'New', wear: 0},
  {id: 'early', name: 'Early service', wear: 0.25},
  {id: 'high', name: 'High time', wear: 0.6},
  {id: 'overhaul', name: 'Overhaul', wear: 1},
];

const ROLE_OF_ALLOY = {
  paintWhite: 'paint', paintGrey: 'paint', paintBlack: 'paint',
  cmsxTbc: 'tbc', cmsxFilm: 'tbc', tbcEffusion: 'tbc',
  inconel718: 'hot', stainlessHot: 'hot', cmc: 'hot', coolPanel: 'hot',
  castIron: 'iron', alCast: 'cast',
  rubber: 'polymer', cfrp: 'polymer', glass: 'skip', cordierite: 'cast',
  honeycomb: 'liner', acoustic: 'liner',
};
const ROLE_ID = {metal: 0, paint: 1, tbc: 2, hot: 3, iron: 4, cast: 5, polymer: 6, liner: 7, carbon: 8};

export const wearUniforms = {
  uWear: {value: 0},
  uY0: {value: 0},
  uY1: {value: 1},
  uScale: {value: 1},
};

const VERT_HEAD = `varying vec3 vWPos; varying float vInst;`;
const VERT_BODY = `
  {
    vec4 wp = vec4(transformed, 1.0);
    #ifdef USE_INSTANCING
      wp = instanceMatrix * wp;
      vInst = fract(sin(dot(instanceMatrix[0].xyz * 3.1 + instanceMatrix[3].xyz * 7.7, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
    #else
      vInst = 0.5;
    #endif
    vWPos = (modelMatrix * wp).xyz;
  }`;
const FRAG_HEAD = `varying vec3 vWPos; varying float vInst;
  uniform float uWear, uY0, uY1, uScale, uRole, uBlade, uSoot;
  float wh3(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
  float wn3(vec3 x) { vec3 i = floor(x); vec3 f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(wh3(i), wh3(i + vec3(1, 0, 0)), f.x), mix(wh3(i + vec3(0, 1, 0)), wh3(i + vec3(1, 1, 0)), f.x), f.y),
               mix(mix(wh3(i + vec3(0, 0, 1)), wh3(i + vec3(1, 0, 1)), f.x), mix(wh3(i + vec3(0, 1, 1)), wh3(i + vec3(1, 1, 1)), f.x), f.y), f.z); }
  float wfbm(vec3 p) { return 0.55 * wn3(p) + 0.3 * wn3(p * 2.7 + 3.1) + 0.15 * wn3(p * 7.3 + 9.2); }`;
const FRAG_BODY = `
  {
    float w = uWear;
    vec3 q = vWPos * uScale;
    float n = wfbm(q * 18.0);
    float nf = wfbm(q * 60.0 + 4.0);
    float low = 1.0 - clamp((vWPos.y - uY0) / max(1e-4, uY1 - uY0), 0.0, 1.0);
    int role = int(uRole + 0.5);
    // per-instance variation: no two blades in a row alike
    diffuseColor.rgb *= 1.0 + (vInst - 0.5) * (0.05 + 0.1 * w);
    roughnessFactor = clamp(roughnessFactor + (vInst - 0.5) * (0.04 + 0.08 * w), 0.02, 1.0);
    // dust everywhere, a little
    roughnessFactor = clamp(roughnessFactor + 0.1 * w * nf, 0.02, 1.0);
    // an oil film collecting in the low places: darker and glossier
    if (role != 6 && role != 7) {
      float oil = w * smoothstep(0.55, 1.05, low * 0.75 + n * 0.55);
      diffuseColor.rgb *= 1.0 - 0.45 * oil;
      roughnessFactor = mix(roughnessFactor, 0.12, 0.65 * oil);
    }
    if (role == 3) {
      // soot builds up in the hottest zones first (uSoot biases by the part's temperature)
      float s = w * smoothstep(0.32, 0.72, n * 0.7 + 0.2 + uSoot * 0.4);
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.05, 0.045, 0.04), 0.8 * s);
      roughnessFactor = mix(roughnessFactor, 0.85, s);
      metalnessFactor = mix(metalnessFactor, 0.15, s);
    } else if (role == 2) {
      // thermal-barrier coating: fades and browns with time, then spalls to the bond coat
      diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * vec3(0.86, 0.8, 0.7), w);
      float th = 0.8 - 0.22 * w;
      float sp = w * smoothstep(th, th + 0.02, wfbm(q * 34.0 + vInst * 13.0));
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.36, 0.33, 0.29), sp);
      metalnessFactor = mix(metalnessFactor, 0.85, sp);
      roughnessFactor = mix(roughnessFactor, 0.5, sp);
    } else if (role == 1) {
      // paint chalks, then chips to bare metal
      diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * 0.9 + 0.04, w);
      roughnessFactor = clamp(roughnessFactor + 0.2 * w, 0.02, 1.0);
      float chip = w * smoothstep(0.72 - 0.06 * w, 0.73 - 0.06 * w, wfbm(q * 260.0 + 1.7)) * smoothstep(0.45, 0.6, n);
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.62, 0.63, 0.64), chip);
      metalnessFactor = mix(metalnessFactor, 1.0, chip);
      roughnessFactor = mix(roughnessFactor, 0.35, chip);
    } else if (role == 4) {
      // cast iron rusts where it is low and wet
      float r = smoothstep(0.82, 1.02, nf * 0.75 + low * 0.45) * max(0.0, (w - 0.3) / 0.7);
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.3, 0.15, 0.07), 0.8 * r);
      roughnessFactor = mix(roughnessFactor, 0.9, r);
      metalnessFactor = mix(metalnessFactor, 0.1, r);
    } else if (role == 5) {
      // aluminium castings dull and pick up a white oxide bloom
      float r = smoothstep(0.8, 1.0, nf * 0.75 + low * 0.35) * max(0.0, (w - 0.4) / 0.6);
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.7, 0.7, 0.68), 0.35 * r);
      roughnessFactor = clamp(roughnessFactor + 0.15 * w + 0.25 * r, 0.02, 1.0);
    } else if (role == 8) {
      // carbon deposits on piston crowns and valves
      float c = w * smoothstep(0.25, 0.75, n + 0.35 * w);
      diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.035, 0.03, 0.028), 0.9 * c);
      roughnessFactor = mix(roughnessFactor, 0.92, c);
      metalnessFactor = mix(metalnessFactor, 0.0, c);
    } else if (role == 7) {
      // liners: the blade tips cut a darker, polished rub track
      float t = w * smoothstep(0.4, 0.8, n);
      diffuseColor.rgb *= 1.0 - 0.3 * t;
    }
    #ifdef USE_NORMALMAP
      if (uBlade > 0.5) {
        // leading-edge erosion: the loft's u runs round the section with the leading edge at 0.5
        float u = fract(vNormalMapUv.x);
        float le = 1.0 - smoothstep(0.0, 0.07, abs(u - 0.5));
        float er = le * w * (0.5 + vInst);
        roughnessFactor = mix(roughnessFactor, 0.78, clamp(er, 0.0, 1.0));
        diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * 1.12, clamp(er, 0.0, 1.0));
      }
    #endif
  }`;

const installed = new Set();
const tinted = [];

/** heat tint for a hot part: the oxide film thickens with temperature (straw, bronze, purple, blue) and with time */
const heatTint = (m, w) => {
  const T = m.userData.T;
  if (!T || !m.isMeshPhysicalMaterial) return;
  const k = Math.max(0, Math.min(1, (T - 450) / 900));
  m.iridescence = Math.min(1, k * (0.12 + 0.88 * w));
  m.iridescenceIOR = 1.8;
  const t0 = 160 + 0.16 * Math.max(0, T - 500) * (0.4 + 0.6 * w);
  m.iridescenceThicknessRange = [t0, t0 + 180 + 120 * w];
};

/**
 * Install wear on every opaque physical material under root. box: the engine's bounds (for the low-surface oil film
 * and the noise scale).
 */
export function applyWear(root, box, wear) {
  wearUniforms.uY0.value = box.min.y;
  wearUniforms.uY1.value = box.max.y;
  wearUniforms.uScale.value = 1 / Math.max(0.1, box.getSize(new THREE.Vector3()).length());
  tinted.length = 0;
  const seen = new Set();
  root.traverse((o) => {
    if (!o.isMesh) return;
    for (const m of [].concat(o.material)) {
      if (!m || seen.has(m) || !m.isMeshStandardMaterial) continue;
      seen.add(m);
      if (m.transparent && !m.userData.shell) continue;
      const role = m.userData.wearRole ?? ROLE_OF_ALLOY[m.userData.alloy] ?? (m.metalness >= 0.5 ? 'metal' : 'polymer');
      if (role === 'skip') continue;
      if (m.userData.T) tinted.push(m);
      if (installed.has(m)) continue;
      installed.add(m);
      const own = {uRole: {value: ROLE_ID[role] ?? 0}, uBlade: {value: m.userData.blade ? 1 : 0}, uSoot: {value: Math.max(0, Math.min(1, ((m.userData.T ?? 0) - 700) / 900))}};
      const prev = m.onBeforeCompile;
      const prevKey = m.customProgramCacheKey?.call(m) ?? '';
      m.onBeforeCompile = (sh, r) => {
        if (prev) prev.call(m, sh, r);
        Object.assign(sh.uniforms, wearUniforms, own);
        sh.vertexShader = sh.vertexShader.replace('#include <common>', `#include <common>\n${VERT_HEAD}`).replace('#include <project_vertex>', `#include <project_vertex>\n${VERT_BODY}`);
        sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>\n${FRAG_HEAD}`).replace('#include <metalnessmap_fragment>', `#include <metalnessmap_fragment>\n${FRAG_BODY}`);
      };
      m.customProgramCacheKey = () => `wear|${prevKey}`;
      m.needsUpdate = true;
    }
  });
  setWear(wear);
}

/** move every part to service state wear in [0, 1] */
export function setWear(wear) {
  wearUniforms.uWear.value = wear;
  for (const m of tinted) heatTint(m, wear);
}

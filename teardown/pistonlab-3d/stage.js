// The teardown V8's studio, moved into the DAS LABS graphite: a near-black backdrop, a faint hairline floor grid,
// bright soft boxes so the metal still reads, a soft shadow, GTAO kept off the floor. setEngine(E) rebuilds the
// geometry for a new solve; frame(th, cam, opts) poses it and draws one frame; pick(x, y) names the part under a pixel.
import * as THREE from 'three';
import {EffectComposer} from 'three/addons/postprocessing/EffectComposer.js';
import {GTAOPass} from 'three/addons/postprocessing/GTAOPass.js';
import {OutputPass} from 'three/addons/postprocessing/OutputPass.js';
import {Pass} from 'three/addons/postprocessing/Pass.js';
import {RenderPass} from 'three/addons/postprocessing/RenderPass.js';
import {ShaderPass} from 'three/addons/postprocessing/ShaderPass.js';
import {UnrealBloomPass} from 'three/addons/postprocessing/UnrealBloomPass.js';
import {BokehPass} from 'three/addons/postprocessing/BokehPass.js';
import {buildEngine} from './engine.js';
import {ENVIRONMENTS, backdrop} from '../shared/environments.js';
import {applyWear, setWear as setWearLevel} from '../shared/wear.js';

const V3 = THREE.Vector3;

export function createStage({canvas}) {
  const renderer = new THREE.WebGLRenderer({canvas, alpha: true, antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance'});
  // AgX rolls highlights off the way film does, so bright metal desaturates instead of clipping to flat colour
  renderer.toneMapping = THREE.AgXToneMapping;
  renderer.toneMappingExposure = 1.3;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.VSMShadowMap;
  renderer.localClippingEnabled = true;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(26, 16 / 9, 0.02, 60);
  const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(4, 4, {type: THREE.HalfFloatType, samples: 8}));
  composer.addPass(new RenderPass(scene, camera));
  const gtao = new GTAOPass(scene, camera, 4, 4);
  gtao.output = GTAOPass.OUTPUT.Default;
  gtao.blendIntensity = 1.0;
  gtao.updateGtaoMaterial({radius: 0.04, distanceExponent: 1.4, thickness: 0.6, scale: 1.0, samples: 16, distanceFallOff: 1.0, screenSpaceRadius: false});
  gtao.updatePdMaterial({lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 16});
  class Toggle extends Pass {
    constructor(fn) {
      super();
      this.needsSwap = false;
      this.fn = fn;
    }
    render() {
      this.fn();
    }
  }
  composer.addPass(new Toggle(() => (shade.visible = false)));
  composer.addPass(gtao);
  composer.addPass(new Toggle(() => (shade.visible = true)));
  // Selective glow. Layer 1 holds what emits light (the flame, the spark, exhaust metal hot enough to glow), layer 2
  // the see-through shells. A half-size pass draws the depth of everything that can hide an emitter, then the
  // emitters alone over it, blurs that, and the result is added to the frame. Specular highlights on polished metal
  // never reach it, however bright they get.
  // layers: 0 everything solid, 1 glow-only twins, 2 see-through shells, 3 light sources seen in both passes
  const mainLayers = () => {
    camera.layers.set(0);
    camera.layers.enable(2);
    camera.layers.enable(3);
  };
  mainLayers();
  let shellsOcclude = false;
  const depthOnly = new THREE.MeshBasicMaterial({colorWrite: false});
  const glowComposer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(4, 4, {type: THREE.HalfFloatType}));
  glowComposer.renderToScreen = false;
  class GlowRender extends Pass {
    constructor() {
      super();
      this.needsSwap = false;
    }
    render(r, _w, read) {
      const bg = scene.background;
      const auto = r.autoClear;
      const shadows = r.shadowMap.autoUpdate;
      const cc = r.getClearColor(new THREE.Color());
      const ca = r.getClearAlpha();
      scene.background = null;
      shade.visible = grid.visible = false;
      r.shadowMap.autoUpdate = false;
      r.setRenderTarget(read);
      r.setClearColor(0x000000, 1);
      r.clear();
      r.autoClear = false;
      camera.layers.set(0);
      if (shellsOcclude) camera.layers.enable(2);
      scene.overrideMaterial = depthOnly;
      r.render(scene, camera);
      scene.overrideMaterial = null;
      eng?.setGlowPass?.(true);
      camera.layers.set(1);
      camera.layers.enable(3);
      r.render(scene, camera);
      eng?.setGlowPass?.(false);
      mainLayers();
      r.autoClear = auto;
      void shadows;
      r.setClearColor(cc, ca);
      scene.background = bg;
      shade.visible = grid.visible = true;
    }
  }
  glowComposer.addPass(new GlowRender());
  const bloom = new UnrealBloomPass(new THREE.Vector2(4, 4), 0.7, 0.5, 0.0);
  glowComposer.addPass(bloom);
  let glowOn = true;
  const mix = new ShaderPass(
    new THREE.ShaderMaterial({
      uniforms: {baseTexture: {value: null}, glowTexture: {value: glowComposer.renderTarget2.texture}, on: {value: 1}, uTime: {value: 0}, uHaze: {value: 1}},
      vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      // plus a lens's gentle fall-off toward the corners (written 1 - smoothstep(a, b) with a < b: ANGLE returns 0
      // for a reversed smoothstep)
      fragmentShader: 'uniform sampler2D baseTexture; uniform sampler2D glowTexture; uniform float on, uTime, uHaze; varying vec2 vUv; float hh(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); } float hn(vec2 p) { vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(hh(i), hh(i + vec2(1, 0)), f.x), mix(hh(i + vec2(0, 1)), hh(i + vec2(1, 1)), f.x), f.y); } void main() { vec3 gl = texture2D(glowTexture, vUv).rgb; float g = clamp(dot(gl, vec3(0.33)) * 1.5, 0.0, 1.0) * on * uHaze; vec2 q = vUv * vec2(90.0, 50.0) + vec2(0.0, -uTime * 3.0); vec2 off = (vec2(hn(q), hn(q + 17.3)) - 0.5) * 0.006 * g; vec4 c = texture2D(baseTexture, vUv + off) + on * vec4(gl, 0.0); float v = 1.0 - smoothstep(0.45, 0.95, length((vUv - 0.5) * vec2(1.2, 1.0))); c.rgb *= mix(0.78, 1.0, v); gl_FragColor = c; }',
    }),
    'baseTexture',
  );
  composer.addPass(mix);
  // depth of field for photo mode: a physical-camera bokeh focused on the camera's target, off otherwise
  const bokeh = new BokehPass(scene, camera, {focus: 1, aperture: 0.002, maxblur: 0.012});
  bokeh.enabled = false;
  let dofAperture = 0.3;
  composer.addPass(bokeh);
  composer.addPass(new OutputPass());

  const sun = new THREE.DirectionalLight('#fff8ee', 2.6);
  sun.position.set(-1.2, 3.2, 1.6);
  sun.castShadow = true;
  Object.assign(sun.shadow.camera, {left: -0.8, right: 0.8, top: 0.8, bottom: -0.8, near: 0.5, far: 8});
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.radius = 12;
  sun.shadow.blurSamples = 20;
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.002;
  scene.add(sun, sun.target);
  // a little sky fill so the shadow sides are not black, and a cool rim behind that lifts the silhouette off the
  // backdrop the way a photographer's kicker does
  const hemi = new THREE.HemisphereLight('#dfe6ee', '#15171b', 0.3);
  scene.add(hemi);
  const rim = new THREE.DirectionalLight('#cfdcf0', 1.3);
  rim.position.set(2.5, 1.2, -2.5);
  scene.add(rim);

  // Image-based light from one of the shared environments (teardown/shared/environments.js): a photo studio, an
  // engine test cell, a maintenance hangar or an overcast sky, each rendered once into a PMREM map and cached. The
  // key, fill and rim lights follow the environment; rotating it turns the reflections, not the lights.
  const envCache = {};
  let envName = 'studio';
  const setEnvironment = (name) => {
    const E = ENVIRONMENTS[name] ?? ENVIRONMENTS.studio;
    envName = ENVIRONMENTS[name] ? name : 'studio';
    if (!envCache[envName]) {
      const pm = new THREE.PMREMGenerator(renderer);
      envCache[envName] = {env: pm.fromScene(E.build(), 0.02).texture, bg: backdrop(E.bg)};
      pm.dispose();
    }
    scene.environment = envCache[envName].env;
    scene.background = envCache[envName].bg;
    scene.environmentIntensity = 0.95;
    sun.color.set(E.sun.color);
    sun.intensity = E.sun.intensity;
    hemi.intensity = E.hemi;
    rim.color.set(E.rim.color);
    rim.intensity = E.rim.intensity;
  };
  const setEnvRotation = (a) => scene.environmentRotation.set(0, a, 0);
  const setExposure = (e) => (renderer.toneMappingExposure = e);
  setEnvironment('studio');

  const shade = new THREE.Mesh(
    new THREE.PlaneGeometry(20, 20),
    new THREE.ShadowMaterial({color: '#000000', opacity: 0.55, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -8}),
  );
  shade.rotation.x = -Math.PI / 2;
  shade.receiveShadow = true;
  scene.add(shade);

  const grid = new THREE.GridHelper(20, 200, '#2a2e35', '#1b1e23');
  grid.material.transparent = true;
  grid.material.opacity = 0.55;
  scene.add(grid);

  let eng = null;
  let wear = 0;
  const setWear = (w) => {
    wear = w;
    setWearLevel(w);
  };
  let lit = []; // [mesh, its own material] while a part is highlighted
  const fit = {center: new V3(), radius: 0.4};
  const setEngine = (E) => {
    lit = [];
    if (eng) {
      scene.remove(eng.root);
      eng.root.traverse((o) => {
        o.geometry?.dispose();
        if (o.material) [].concat(o.material).forEach((m) => m.dispose());
      });
    }
    eng = buildEngine(E);
    for (const o of eng.glowers) o.layers.set(o.userData.spark ? 3 : 1);
    eng.root.traverse((o) => {
      if (o.isMesh && o.material?.userData?.shell) o.layers.set(2);
    });
    scene.add(eng.root);
    // frame the engine at TDC of cylinder 1 (pistons at their highest, so the box holds every pose)
    eng.update(E.cyl[0].fire);
    const box = new THREE.Box3().setFromObject(eng.root);
    box.getCenter(fit.center);
    fit.radius = box.getSize(new V3()).length() / 2;
    shade.position.y = box.min.y - 0.002;
    grid.position.y = box.min.y - 0.003;
    const R = fit.radius;
    Object.assign(sun.shadow.camera, {left: -R * 1.4, right: R * 1.4, top: R * 1.4, bottom: -R * 1.4});
    sun.shadow.camera.updateProjectionMatrix();
    sun.target.position.copy(fit.center);
    sun.position.copy(fit.center).add(new V3(-1.2, 3.2, 1.6));
    gtao.updateGtaoMaterial({radius: 0.08 * R});
    // service state: wear shading on every part, keyed to the engine's bounds
    applyWear(eng.root, box, wear);
    lodCollect();
    shadowDirty = true;
    return eng;
  };

  const size = {w: 1600, h: 900};
  const resize = (w, h, pr) => {
    size.w = w;
    size.h = h;
    renderer.setPixelRatio(pr);
    renderer.setSize(w, h, false);
    composer.setPixelRatio(pr);
    composer.setSize(w, h);
    glowComposer.setPixelRatio(pr);
    glowComposer.setSize(Math.max(1, Math.round(w / 2)), Math.max(1, Math.round(h / 2)));
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  // cam: azimuth from +z toward +x, elevation, zoom k (1 frames the whole engine), sx screen shift in px
  // Performance. The shadow map is the costliest extra pass (every caster drawn again), and rotating blades or a
  // moving piston shift the floor shadow by a pixel or two a frame, so it is redrawn every few frames (by quality
  // tier) and whenever the model changes; a still redraws it every sample. Small parts (bolts, clips, probes,
  // sensors) are skipped once they shrink below about 1.5 px on screen, in every pass.
  let shadowEvery = 4;
  let shadowDirty = true;
  let frameNo = 0;
  const setShadowEvery = (n) => {
    shadowEvery = n;
    shadowDirty = true;
  };
  const markShadows = () => (shadowDirty = true);
  let lodParts = [];
  const lodCollect = () => {
    lodParts = [];
    const lim = 0.012 * fit.radius;
    eng.root.traverse((o) => {
      if (!o.isMesh || o.userData.spark || o.userData.cap) return;
      const g = o.geometry;
      if (!g.boundingSphere) g.computeBoundingSphere();
      const r = g.boundingSphere.radius * Math.max(o.scale.x, o.scale.y, o.scale.z);
      if (r < lim && r > 0) {
        if (o.isInstancedMesh) o.computeBoundingSphere();
        lodParts.push({o, size: 2 * r});
      }
    });
  };
  const lodV = new V3();
  const lodUpdate = () => {
    const f = size.h / (2 * Math.tan((camera.fov * Math.PI) / 360));
    for (const L of lodParts) {
      const o = L.o;
      const bs = o.isInstancedMesh ? o.boundingSphere : o.geometry.boundingSphere;
      lodV.copy(bs.center).applyMatrix4(o.matrixWorld);
      const dist = Math.max(1e-3, camera.position.distanceTo(lodV) - (o.isInstancedMesh ? bs.radius : 0));
      const show = (L.size * f) / dist > 1.5;
      if (o.visible !== show) {
        o.visible = show;
        shadowDirty = true;
      }
    }
  };
  const frame = (th, cam, opts = {}) => {
    eng.update(th, opts);
    frameNo++;
    renderer.shadowMap.autoUpdate = false;
    if (shadowDirty || st.hold || (shadowEvery > 0 && frameNo % shadowEvery === 0)) {
      renderer.shadowMap.needsUpdate = true;
      shadowDirty = false;
    }
    // distance that fits the engine's bounding sphere in the narrower field of view
    const vf = (camera.fov * Math.PI) / 360;
    const hf = Math.atan(Math.tan(vf) * camera.aspect);
    const d = (fit.radius / Math.sin(Math.min(vf, hf))) * 1.02 * cam.k * (cam.fill ?? 1);
    const {az, el} = cam;
    const c = cam.target ?? fit.center;
    camera.position.set(c.x + d * Math.cos(el) * Math.sin(az), c.y + d * Math.sin(el), c.z + d * Math.cos(el) * Math.cos(az));
    camera.lookAt(c);
    camera.setViewOffset(size.w, size.h, -(cam.sx ?? 0), -(cam.sy ?? 0), size.w, size.h);
    camera.updateMatrixWorld();
    lodUpdate();
    if (bokeh.enabled) {
      bokeh.uniforms.focus.value = d;
      bokeh.uniforms.aperture.value = (0.0004 + 0.008 * dofAperture) / Math.max(0.2, fit.radius);
    }
    // heat haze: refraction in the hot gas, strongest where the glow is (flames, plumes, glowing metal)
    mix.uniforms.uTime.value = performance.now() / 1000;
    if (glowOn) glowComposer.render();
    composer.render();
  };
  const setQuality = ({samples, ao, shadow, glow}) => {
    if (glow !== undefined) {
      glowOn = glow;
      mix.uniforms.on.value = glow ? 1 : 0;
    }
    if (samples !== undefined) {
      for (const t of [composer.renderTarget1, composer.renderTarget2]) {
        t.samples = samples;
        t.dispose();
      }
    }
    if (ao !== undefined) gtao.enabled = ao;
    if (shadow !== undefined) {
      sun.shadow.mapSize.set(shadow, shadow);
      sun.shadow.map?.dispose();
      sun.shadow.map = null;
    }
  };
  const setCut = (mode, z) => {
    eng.setCut(mode, z);
    shellsOcclude = mode !== 'glass';
    depthOnly.clippingPlanes = mode === 'section' ? [eng.CLIP] : null;
    depthOnly.needsUpdate = true;
    gtao.normalMaterial.clippingPlanes = mode === 'section' ? [eng.CLIP] : null;
    gtao.normalMaterial.needsUpdate = true;
  };
  // the part under a screen point: hidden layers and faint glass shells (in glass mode) do not catch the click
  const ray = new THREE.Raycaster();
  ray.layers.enableAll();
  const ndc = new THREE.Vector2();
  const shown = (o) => {
    for (let x = o; x; x = x.parent) if (!x.visible) return false;
    return true;
  };
  const pick = (x, y) => {
    ndc.set((x / size.w) * 2 - 1, -(y / size.h) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hits = ray.intersectObject(eng.root, true).filter((h) => (h.object.isMesh || h.object.isInstancedMesh) && shown(h.object));
    const solid = hits.find((h) => !(h.object.material.transparent && h.object.material.opacity < 0.3));
    const h = solid || hits[0];
    if (!h) return null;
    for (let o = h.object; o; o = o.parent) if (o.userData.pick) return {obj: o, ...o.userData.pick};
    return null;
  };
  // highlight a part by swapping its meshes onto glowing copies of their materials
  const highlight = (obj) => {
    for (const [m, orig] of lit) m.material = orig;
    lit = [];
    if (!obj) return;
    obj.traverse((m) => {
      if (!m.isMesh) return;
      const c = m.material.clone();
      if (c.emissive) {
        c.emissive.set('#e8923e');
        c.emissiveIntensity = 0.55;
      }
      lit.push([m, m.material]);
      m.material = c;
    });
  };
  /** centre and radius of an object's bounds, for flying the camera to a part */
  const focusOf = (obj) => {
    const b = new THREE.Box3().setFromObject(obj);
    return {center: b.getCenter(new V3()), radius: b.getSize(new V3()).length() / 2};
  };
  const setHaze = (on) => (mix.uniforms.uHaze.value = on ? 1 : 0);
  // photo mode: focal length (35 mm equivalent, so the vertical field is 2 atan(12 / f)), depth of field, and a
  // transparent background (no backdrop, no floor, alpha left clear)
  const setFocal = (f) => {
    camera.fov = (2 * Math.atan(12 / f) * 180) / Math.PI;
    camera.updateProjectionMatrix();
  };
  const setDOF = (on, a = dofAperture) => {
    bokeh.enabled = on;
    dofAperture = a;
  };
  const floorOpacity = [shade.material.opacity, grid.material.opacity];
  // matte: render over a plain black (or white) clear, no backdrop, no floor; photo mode pulls alpha from the pair
  const setTransparent = (on, white = false) => {
    scene.background = on ? null : envCache[envName].bg;
    shade.material.opacity = on ? 0 : floorOpacity[0];
    grid.material.opacity = on ? 0 : floorOpacity[1];
    renderer.setClearColor(on && white ? 0xffffff : 0x000000, 1);
  };
  const st = {setShadowEvery, markShadows, setHaze, setFocal, setDOF, setTransparent, hold: false, renderer, scene, camera, composer, resize, frame, setEngine, setQuality, setCut, pick, highlight, focusOf, fit, size, setEnvironment, setEnvRotation, setExposure, setWear, get envName() {
    return envName;
  }, get eng() {
    return eng;
  }};
  return st;
}

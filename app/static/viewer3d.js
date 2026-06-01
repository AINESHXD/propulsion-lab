/* PropulsionLab — 3D engine viewing suite.
 *
 * A focused viewer for the Blender-built engine models (turbofan, turbojet,
 * ramjet, scramjet), each loaded as a glTF cutaway with hover-to-explain
 * station labels. PBR (neutral studio IBL, ACES, sRGB), orbit + cinematic
 * camera. (Exploded view, field overlays and airflow are reserved for a
 * future Pro build and intentionally not present here.)
 */

import * as THREE from "three";
import { OrbitControls } from "/lab/vendor/three/OrbitControls.js";
import { GLTFLoader } from "/lab/vendor/three/GLTFLoader.js";

const gsap = window.gsap;
const MODEL_VERSION = "?m=5";   // bump when a .glb is re-exported (cache-bust)

// Engine catalogue: model + station labels with hover explanations.
const ENGINES = {
  turbofan: {
    label: "Turbofan",
    url: "/lab/models/jet_engine_cutaway.glb",
    blurb: "High-bypass turbofan — a large fan provides most of the thrust. Efficient and quiet at subsonic cruise.",
    stations: [
      { name: "Fan", t: 0.05, text: "A large fan accelerates a big mass of bypass air, giving most of the thrust at high propulsive efficiency." },
      { name: "Compressor", t: 0.30, text: "Multi-stage axial compressor raises the core-air pressure before combustion." },
      { name: "Combustor", t: 0.52, text: "Fuel burns at roughly constant pressure, adding energy to the core flow." },
      { name: "Turbine", t: 0.67, text: "Hot gas expands through the turbine, extracting work to drive the fan and compressor." },
      { name: "Nozzle", t: 0.90, text: "The core jet accelerates through the nozzle, adding to the bypass thrust." },
    ],
  },
  turbojet: {
    label: "Turbojet",
    url: "/lab/models/jet_engine_turbojet.glb",
    blurb: "Turbojet — all air passes through the core. Simple and capable of high speed, but thirsty at low speed.",
    stations: [
      { name: "Inlet", t: 0.05, text: "Incoming air is diffused and slowed, raising its pressure ahead of the compressor." },
      { name: "Compressor", t: 0.30, text: "Axial stages compress the air to the design pressure ratio." },
      { name: "Combustor", t: 0.54, text: "Fuel is injected and burned, adding heat at nearly constant pressure." },
      { name: "Turbine", t: 0.70, text: "Expansion through the turbine drives the compressor on the shared shaft." },
      { name: "Nozzle", t: 0.90, text: "Remaining energy accelerates the exhaust to produce thrust." },
    ],
  },
  ramjet: {
    label: "Ramjet",
    url: "/lab/models/jet_engine_ramjet.glb",
    blurb: "Ramjet — no moving compressor. Ram compression only works once already flying supersonically.",
    stations: [
      { name: "Inlet spike", t: 0.08, text: "A centre-body spike sets up shock waves that compress the supersonic air — no rotating compressor is needed." },
      { name: "Diffuser", t: 0.32, text: "The diverging duct slows the flow toward subsonic, trading speed for pressure." },
      { name: "Combustor", t: 0.58, text: "Fuel burns behind flame holders. A ramjet makes no static thrust and must be boosted up to speed first." },
      { name: "Nozzle", t: 0.88, text: "A convergent–divergent nozzle expands the hot gas back to supersonic for thrust." },
    ],
  },
  scramjet: {
    label: "Scramjet",
    url: "/lab/models/jet_engine_scramjet.glb",
    blurb: "Scramjet — a supersonic-combustion ramjet for hypersonic flight. The air never slows to subsonic.",
    stations: [
      { name: "Inlet", t: 0.10, text: "Sharp compression surfaces compress the air while keeping the whole flow supersonic." },
      { name: "Isolator", t: 0.35, text: "A constant-area duct contains the shock train and isolates the inlet from combustor pressure rises." },
      { name: "Combustor", t: 0.58, text: "Fuel injected from struts burns in milliseconds — combustion happens in supersonic flow." },
      { name: "Nozzle", t: 0.86, text: "The long expansion surface accelerates the exhaust, producing thrust at hypersonic speed." },
    ],
  },
  turboprop: {
    label: "Turboprop",
    url: "/lab/models/jet_engine_turboprop.glb",
    blurb: "Turboprop — a gas-generator core drives a large propeller through a gearbox. Most efficient at low-to-mid subsonic speeds.",
    stations: [
      { name: "Propeller", t: 0.09, text: "A large propeller produces most of the thrust; the engine core mainly exists to spin it efficiently." },
      { name: "Gearbox", t: 0.20, text: "A reduction gearbox steps the high turbine RPM down to an efficient propeller speed." },
      { name: "Compressor", t: 0.40, text: "Axial stages compress the core air for the gas generator." },
      { name: "Combustor", t: 0.56, text: "Fuel burns, driving both the gas-generator and the power turbine." },
      { name: "Power turbine", t: 0.70, text: "A free (power) turbine extracts shaft work to drive the propeller — separate from the gas-generator spool." },
      { name: "Exhaust", t: 0.87, text: "Only a small residual jet remains; nearly all the energy has gone to the propeller." },
    ],
  },
};

export function startViewer() {
  const fail = (msg) => {
    const f = document.getElementById("fallback");
    if (f) { f.style.display = "flex"; const r = f.querySelector("[data-reason]"); if (r) r.textContent = msg; }
    ["panel", "toolbar", "info"].forEach((id) => { const el = document.getElementById(id); if (el) el.style.display = "none"; });
  };
  try {
    const c = document.createElement("canvas");
    if (!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")))) return fail("This device doesn't expose WebGL.");
  } catch { return fail("WebGL could not be initialised."); }
  try { window.PLViewer = new Viewer(); } catch (err) { console.error(err); fail(String((err && err.message) || err)); }
}

class Viewer {
  constructor() {
    this.canvas = document.getElementById("scene");
    this.reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.models = {};   // engine key -> { scene, span, maxY }
    this.labels = [];
    this.engine = null;
    this._loading = {};

    this._initRenderer();
    this._initScene();
    this._initEnvironment();
    this._initLights();
    this._initControls();
    this._initUI();
    this._initKeys();
    this._resize();
    window.addEventListener("resize", () => this._resize());
    this._animate();

    const params = new URLSearchParams(location.search);
    this.embed = params.has("embed");          // compact, UI-less showcase (e.g. hero iframe)
    if (this.embed) {
      ["panel", "toolbar", "info"].forEach((id) => { const e = document.getElementById(id); if (e) e.style.display = "none"; });
      const tb = document.querySelector(".topbar"); if (tb) tb.style.display = "none";
      this.controls.enableZoom = false; this.controls.enablePan = false; this.controls.autoRotateSpeed = 0.8;
      this.scene.background = new THREE.Color(0x0a0b0e);      // match the hero so the panel blends seamlessly
      if (this.scene.fog) this.scene.fog.color.set(0x0a0b0e);
    }
    const q = params.get("engine");
    this.select(ENGINES[q] ? q : "turbofan");
  }

  _initRenderer() {
    const r = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, powerPreference: "high-performance", stencil: false });
    r.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    r.toneMapping = THREE.ACESFilmicToneMapping;
    r.toneMappingExposure = 1.3;
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer = r;
  }

  _initScene() {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x090a0d);
    this.scene.fog = new THREE.Fog(0x090a0d, 26, 60);
    this.camera = new THREE.PerspectiveCamera(38, 1, 0.1, 200);
    this.camera.position.set(8, 3.8, 16.5);
  }

  _initEnvironment() {
    // Neutral, near-uniform grey studio IBL: even metal reflections, no colour cast.
    const cv = document.createElement("canvas"); cv.width = 32; cv.height = 128;
    const ctx = cv.getContext("2d");
    const g = ctx.createLinearGradient(0, 0, 0, 128);
    g.addColorStop(0.0, "#d2d6db"); g.addColorStop(0.5, "#c4c8ce"); g.addColorStop(1.0, "#b4b8bf");
    ctx.fillStyle = g; ctx.fillRect(0, 0, 32, 128);
    const tex = new THREE.CanvasTexture(cv);
    tex.mapping = THREE.EquirectangularReflectionMapping; tex.colorSpace = THREE.SRGBColorSpace;
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromEquirectangular(tex).texture;
    pmrem.dispose(); tex.dispose();
  }

  _initLights() {
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.66));
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x40454d, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 2.8);
    key.position.set(6, 9, 7); key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    Object.assign(key.shadow.camera, { near: 1, far: 42, left: -11, right: 11, top: 11, bottom: -11 });
    key.shadow.bias = -0.0004;
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0xdfe6f0, 0.9); fill.position.set(-7, 2, -6); this.scene.add(fill);
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.ShadowMaterial({ opacity: 0.32 }));
    ground.rotation.x = -Math.PI / 2; ground.position.y = -2.4; ground.receiveShadow = true;
    this.scene.add(ground);
  }

  _initControls() {
    const c = new OrbitControls(this.camera, this.canvas);
    c.enableDamping = true; c.dampingFactor = 0.06; c.minDistance = 3.0; c.maxDistance = 40;
    c.autoRotate = !this.reduceMotion; c.autoRotateSpeed = 0.5; c.target.set(0, 0, 0);
    this.controls = c;
  }

  // ---- Model loading + selection ----------------------------------------
  select(engine) {
    if (!ENGINES[engine]) return;
    this.engine = engine;
    const cfg = ENGINES[engine];
    Object.values(this.models).forEach((m) => { m.scene.visible = false; });
    if (this.ui && this.ui.engine) this.ui.engine.value = engine;
    const blurb = document.getElementById("engineBlurb");
    if (blurb) blurb.textContent = cfg.blurb;
    const info = document.getElementById("info");
    this._buildLabels(cfg);
    this._syncUrl(engine);
    this._hideTip();

    if (!this.models[engine] && info) info.innerHTML = `Loading ${cfg.label}…`;
    this._loadModel(engine, (rec) => {
      if (this.engine !== engine) return;        // user switched away while loading
      rec.scene.visible = true;
      this._frame(rec);
      if (info) info.innerHTML = `<b>${cfg.label}</b> · hover a label · <span style="opacity:.7">←/→ to switch</span>`;
      this._preloadRest();                       // warm the rest once the first is on screen
    });
  }

  // Load (or reuse) a model. Callbacks queue so concurrent requests share one fetch.
  _loadModel(engine, onReady) {
    const cfg = ENGINES[engine];
    if (this.models[engine]) { if (onReady) onReady(this.models[engine]); return; }
    if (this._loading[engine]) { if (onReady) this._loading[engine].push(onReady); return; }
    this._loading[engine] = onReady ? [onReady] : [];
    new GLTFLoader().load(cfg.url + MODEL_VERSION, (gltf) => {
      const s = gltf.scene;
      const slim = (engine === "ramjet" || engine === "scramjet"); // slim dark bodies read dark — lift them
      s.traverse((o) => {
        if (!o.isMesh) return;
        o.castShadow = true; o.receiveShadow = true;
        const m = o.material; if (!m) return;
        m.envMapIntensity = slim ? 2.4 : 1.25;
        if (slim && m.color) {
          if ((m.color.r + m.color.g + m.color.b) / 3 < 0.22) m.color.setRGB(0.34, 0.35, 0.38); // lift near-black spike/centre-body
          if (m.metalness != null) m.metalness = Math.min(m.metalness, 0.82);
          if (m.roughness != null) m.roughness = Math.max(m.roughness, 0.5);
        }
      });
      s.visible = false;
      this.scene.add(s);
      s.updateMatrixWorld(true);
      s.position.sub(new THREE.Box3().setFromObject(s).getCenter(new THREE.Vector3()));
      s.updateMatrixWorld(true);
      const b = new THREE.Box3().setFromObject(s);
      const rec = { scene: s, span: b.max.x - b.min.x, maxY: b.max.y };
      this.models[engine] = rec;
      const cbs = this._loading[engine] || []; this._loading[engine] = null;
      cbs.forEach((cb) => cb && cb(rec));
    }, undefined, (err) => {
      console.error(err);
      this._loading[engine] = null;
      const info = document.getElementById("info");
      if (info && this.engine === engine) info.innerHTML = `${cfg.label} model failed to load.`;
    });
  }

  // After the first visible model, quietly warm the other engines so switching is instant.
  _preloadRest() {
    if (this.embed || this._preloaded) return;
    this._preloaded = true;
    const rest = Object.keys(ENGINES).filter((k) => k !== this.engine);
    const next = () => { const k = rest.shift(); if (!k) return; this._loadModel(k, () => setTimeout(next, 150)); };
    (window.requestIdleCallback || ((f) => setTimeout(f, 900)))(() => next());
  }

  _syncUrl(engine) {
    if (this.embed) return;
    try { const u = new URL(location.href); u.searchParams.set("engine", engine); history.replaceState(null, "", u); } catch { /* ignore */ }
  }

  _frame(rec) {
    const half = Math.tan((this.camera.fov * Math.PI / 180) / 2);
    let dist;
    if (this.embed) {
      // Fit the engine's BOUNDING SPHERE to the smaller viewport dimension —
      // orientation-independent, so nothing ever clips while it auto-rotates,
      // regardless of panel aspect or layout timing.
      const R = 0.5 * Math.sqrt(rec.span * rec.span + 2 * (2 * rec.maxY) * (2 * rec.maxY));
      const vfov = (this.camera.fov * Math.PI) / 180;
      const hfov = 2 * Math.atan(Math.tan(vfov / 2) * (this.camera.aspect || 1.25));
      dist = Math.max(R / Math.sin(vfov / 2), R / Math.sin(hfov / 2)) * 1.04;
    } else {
      dist = (Math.max(rec.span, rec.maxY * 1.6) / (2 * half)) * 1.28;
    }
    const dir = new THREE.Vector3(0.42, 0.26, 1).normalize().multiplyScalar(dist);
    this._cameraTo(dir, new THREE.Vector3(0, 0, 0), 1.1);
  }

  _cameraTo(camPos, target, dur) {
    const wasAuto = this.controls.autoRotate;
    this.controls.autoRotate = false;            // avoid fighting the tween
    if (!gsap) { this.camera.position.copy(camPos); this.controls.target.copy(target); this.controls.autoRotate = wasAuto; return; }
    gsap.to(this.camera.position, { x: camPos.x, y: camPos.y, z: camPos.z, duration: dur, ease: "power3.inOut", onComplete: () => { this.controls.autoRotate = wasAuto; } });
    gsap.to(this.controls.target, { x: target.x, y: target.y, z: target.z, duration: dur, ease: "power3.inOut", onUpdate: () => this.controls.update() });
  }

  // ---- Station labels + hover explanations ------------------------------
  _buildLabels(cfg) {
    if (this.embed) { this.labels = []; return; }   // no labels in the compact showcase
    const cont = document.getElementById("labels");
    this.labels.forEach((l) => l.el.remove());
    this.labels = cfg.stations.map((st) => {
      const el = document.createElement("button");
      el.className = "station-label";
      el.textContent = st.name;
      el.addEventListener("mouseenter", () => this._showTip(st, el));
      el.addEventListener("focus", () => this._showTip(st, el));
      el.addEventListener("mouseleave", () => this._hideTip());
      el.addEventListener("blur", () => this._hideTip());
      el.addEventListener("click", () => { this._showTip(st, el); this._focus(st); }); // tap = explain + fly-to (touch)
      cont.appendChild(el);
      return { el, st };
    });
  }

  _showTip(st, el) {
    const tip = document.getElementById("tooltip");
    if (!tip) return;
    tip.querySelector("[data-tip-title]").textContent = st.name;
    tip.querySelector("[data-tip-body]").textContent = st.text;
    tip.style.display = "block";
    const r = el.getBoundingClientRect();
    const tw = tip.offsetWidth || 260, th = tip.offsetHeight || 96;
    let left = r.left + r.width / 2 - tw / 2;
    left = Math.max(12, Math.min(left, window.innerWidth - tw - 12));
    let top = r.bottom + 8;
    if (top + th > window.innerHeight - 12) top = Math.max(12, r.top - th - 8); // flip above when it would clip the bottom
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
  }

  _hideTip() { const tip = document.getElementById("tooltip"); if (tip) tip.style.display = "none"; }

  _focus(st) {
    const rec = this.models[this.engine]; if (!rec) return;
    const ax = (st.t - 0.5) * rec.span;
    if (this.ui.present) this.ui.present.classList.remove("on");
    this.controls.autoRotate = false;
    this._cameraTo(new THREE.Vector3(ax + rec.span * 0.16, rec.maxY * 1.3, rec.span * 0.62), new THREE.Vector3(ax, 0, 0), 0.9);
  }

  _updateLabels() {
    const rec = this.models[this.engine]; if (!rec || !rec.scene.visible) { this.labels.forEach(({ el }) => { el.style.display = "none"; }); return; }
    const r = this.canvas.getBoundingClientRect(), v = new THREE.Vector3();
    this.labels.forEach(({ el, st }) => {
      const ax = (st.t - 0.5) * rec.span;
      const labelY = Math.min(rec.maxY, rec.span * 0.18) + 0.18; // cap to body height (don't float at prop-tip)
      v.set(ax, labelY, 0).project(this.camera);
      const behind = v.z > 1;
      el.style.display = behind ? "none" : "block";
      el.style.left = `${r.left + (v.x * 0.5 + 0.5) * r.width}px`;
      el.style.top = `${r.top + (-v.y * 0.5 + 0.5) * r.height}px`;
    });
  }

  // ---- UI ----------------------------------------------------------------
  _initUI() {
    const $ = (id) => document.getElementById(id);
    this.ui = { engine: $("engine"), present: $("present"), reset: $("reset") };
    this.ui.engine.addEventListener("change", () => this.select(this.ui.engine.value));
    this.ui.present.addEventListener("click", () => { this.controls.autoRotate = !this.controls.autoRotate; this.ui.present.classList.toggle("on", this.controls.autoRotate); });
    this.ui.present.classList.toggle("on", this.controls.autoRotate);
    if (this.ui.reset) this.ui.reset.addEventListener("click", () => {
      const rec = this.models[this.engine]; if (!rec) return;
      this.controls.autoRotate = !this.reduceMotion;
      this.ui.present.classList.toggle("on", this.controls.autoRotate);
      this._frame(rec);
    });
    // Tapping/clicking the model (anywhere but a label) dismisses an open tooltip.
    this.canvas.addEventListener("pointerdown", () => this._hideTip());
  }

  // Keyboard: ←/→ (or ↑/↓) cycle engines, 1–5 jump directly, R resets the view.
  _initKeys() {
    if (this.embed) return;
    const keys = Object.keys(ENGINES);
    window.addEventListener("keydown", (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target;
      if (t && /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName)) return; // let form controls keep their keys
      const i = keys.indexOf(this.engine);
      if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); this.select(keys[(i + 1) % keys.length]); }
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); this.select(keys[(i - 1 + keys.length) % keys.length]); }
      else if (/^[1-9]$/.test(e.key)) { const k = keys[parseInt(e.key, 10) - 1]; if (k) { e.preventDefault(); this.select(k); } }
      else if (e.key === "r" || e.key === "R") { if (this.ui.reset) this.ui.reset.click(); }
    });
  }

  _resize() {
    const w = window.innerWidth, h = window.innerHeight;
    this.renderer.setSize(w, h);   // updateStyle=true so the canvas tracks the window at any devicePixelRatio
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
    // Re-fit the embedded showcase if the panel size changed after first layout.
    if (this.embed && this.engine && this.models[this.engine]) this._frame(this.models[this.engine]);
  }

  _animate() {
    const loop = () => {
      requestAnimationFrame(loop);
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
      this._updateLabels();
    };
    requestAnimationFrame(loop);
  }

  dispose() {
    Object.values(this.models).forEach((m) => m.scene.traverse((o) => { if (o.geometry) o.geometry.dispose(); }));
    this.renderer.dispose();
  }
}

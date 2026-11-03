// Photo mode, shared by the JetLab and PistonLab 3D viewers: hides the interface, offers camera presets, a focal
// length (35 mm equivalent), depth of field, exposure and environment rotation, and exports a still. The still is
// rendered at the export size (up to 3840 x 2160) and accumulated over N sub-pixel-jittered frames, so edges come
// out clean; with a transparent background the backdrop and floor drop out of the PNG.
//
// ctx: {st, cam, camTo, app, takeOver, presets: [{name, az, el, k, target?: () => Vector3}], renderFrame(jx, jy, fill),
//       restore(), name()}
export function initPhoto(ctx) {
  const {st, cam, camTo, app} = ctx;
  const el = (tag, cls, html) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  };
  const panel = el('section', 'photo-panel panel', `
    <div class="phead"><b>Photo mode</b><button class="x" id="ph-close" aria-label="Leave photo mode">&times;</button></div>
    <div class="lbl">Camera</div>
    <div class="quick" id="ph-presets"></div>
    <label class="envrow"><span class="lbl">Focal</span><input type="range" id="ph-focal" min="24" max="135" value="52" aria-label="Focal length"><span class="mono" id="ph-focal-v">52 mm</span></label>
    <label class="envrow"><span class="lbl">Exposure</span><input type="range" id="ph-exp" min="60" max="200" value="130" aria-label="Exposure"><span class="mono" id="ph-exp-v">1.30</span></label>
    <label class="envrow"><span class="lbl">Env. rotate</span><input type="range" id="ph-rot" min="0" max="360" value="0" aria-label="Rotate the environment"><span class="mono" id="ph-rot-v">0°</span></label>
    <label class="layer"><input type="checkbox" id="ph-dof"><span>Depth of field</span></label>
    <label class="envrow"><span class="lbl">Aperture</span><input type="range" id="ph-ap" min="1" max="100" value="30" aria-label="Aperture"><span class="mono" id="ph-ap-v"></span></label>
    <div class="lbl">Export</div>
    <div class="quick" id="ph-size"></div>
    <label class="envrow"><span class="lbl">Samples</span><input type="range" id="ph-n" min="1" max="64" value="16" aria-label="Samples"><span class="mono" id="ph-n-v">16</span></label>
    <label class="layer"><input type="checkbox" id="ph-alpha"><span>Transparent background</span></label>
    <button id="ph-go" class="primary">Render still</button>
    <div class="cycstat mono" id="ph-stat"></div>`);
  panel.hidden = true;
  app.appendChild(panel);
  const $ = (id) => document.getElementById(id);
  let active = false;
  let size = '1080p';
  const SIZES = {'1080p': [1920, 1080], '1440p': [2560, 1440], '4K': [3840, 2160]};

  const enter = () => {
    ctx.takeOver();
    active = true;
    document.body.classList.add('photo');
    panel.hidden = false;
    st.setDOF(Boolean($('ph-dof').checked), Number($('ph-ap').value) / 100);
  };
  const leave = () => {
    active = false;
    document.body.classList.remove('photo');
    panel.hidden = true;
    st.setDOF(false);
    st.setFocal(52);
  };
  $('ph-close').onclick = leave;
  addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && active) leave();
  });

  const box = $('ph-presets');
  for (const p of ctx.presets()) {
    const b = el('button', null, p.name);
    b.onclick = () => {
      ctx.takeOver();
      Object.assign(camTo, {az: p.az, el: p.el, k: p.k});
      camTo.target = p.target ? p.target() : null;
      if (camTo.target && !cam.target) cam.target = st.fit.center.clone();
    };
    box.appendChild(b);
  }
  $('ph-focal').oninput = (e) => {
    st.setFocal(Number(e.target.value));
    $('ph-focal-v').textContent = `${e.target.value} mm`;
  };
  $('ph-exp').oninput = (e) => {
    st.setExposure(Number(e.target.value) / 100);
    $('ph-exp-v').textContent = (Number(e.target.value) / 100).toFixed(2);
  };
  $('ph-rot').oninput = (e) => {
    st.setEnvRotation((Number(e.target.value) * Math.PI) / 180);
    $('ph-rot-v').textContent = `${e.target.value}°`;
  };
  const dof = () => {
    st.setDOF(Boolean($('ph-dof').checked), Number($('ph-ap').value) / 100);
    $('ph-ap-v').textContent = `f/${(22 - 20 * (Number($('ph-ap').value) / 100)).toFixed(1)}`;
  };
  $('ph-dof').onchange = dof;
  $('ph-ap').oninput = dof;
  dof();
  const sizes = $('ph-size');
  const renderSizes = () => {
    sizes.innerHTML = '';
    for (const k of Object.keys(SIZES)) {
      const b = el('button', null, k);
      b.setAttribute('aria-pressed', String(size === k));
      b.onclick = () => {
        size = k;
        renderSizes();
      };
      sizes.appendChild(b);
    }
  };
  renderSizes();
  $('ph-n').oninput = (e) => ($('ph-n-v').textContent = e.target.value);

  // the still: N frames at the export size, each shifted by a sub-pixel offset from a Halton sequence, averaged
  const halton = (i, b) => {
    let f = 1;
    let r = 0;
    while (i > 0) {
      f /= b;
      r += f * (i % b);
      i = Math.floor(i / b);
    }
    return r;
  };
  let rendering = false;
  $('ph-go').onclick = async () => {
    if (rendering) return;
    rendering = true;
    const [w, h] = SIZES[size];
    const n = Number($('ph-n').value);
    const alpha = $('ph-alpha').checked;
    const stat = $('ph-stat');
    st.hold = true;
    st.resize(w, h, 1);
    const c2 = document.createElement('canvas');
    c2.width = w;
    c2.height = h;
    const g = c2.getContext('2d', {willReadFrequently: true});
    // the post-processing chain does not carry alpha, so a transparent still is pulled by difference matting: each
    // sample is rendered over black and over white; where the two agree the pixel is opaque, and the background's
    // own difference sets full transparency
    const acc = new Uint16Array(w * h * 4);
    const accW = alpha ? new Uint16Array(w * h * 4) : null;
    const grab = (into) => {
      g.clearRect(0, 0, w, h);
      g.drawImage(st.renderer.domElement, 0, 0, w, h);
      const d = g.getImageData(0, 0, w, h).data;
      for (let j = 0; j < d.length; j++) into[j] += d[j];
    };
    try {
      for (let i = 0; i < n; i++) {
        const jx = halton(i + 1, 2) - 0.5;
        const jy = halton(i + 1, 3) - 0.5;
        if (alpha) {
          st.setTransparent(true, false);
          ctx.renderFrame(jx, jy);
          grab(acc);
          st.setTransparent(true, true);
          ctx.renderFrame(jx, jy);
          grab(accW);
        } else {
          ctx.renderFrame(jx, jy);
          grab(acc);
        }
        stat.textContent = `Sample ${i + 1} of ${n} at ${w} x ${h}`;
        await new Promise((r) => setTimeout(r, 0));
      }
      const img = g.createImageData(w, h);
      if (alpha) {
        let dmax = 1;
        for (let j = 0; j < acc.length; j += 4) dmax = Math.max(dmax, (accW[j] + accW[j + 1] + accW[j + 2] - acc[j] - acc[j + 1] - acc[j + 2]) / 3);
        for (let j = 0; j < acc.length; j += 4) {
          const a = Math.min(1, Math.max(0, 1 - (accW[j] + accW[j + 1] + accW[j + 2] - acc[j] - acc[j + 1] - acc[j + 2]) / 3 / dmax));
          for (let c = 0; c < 3; c++) img.data[j + c] = a > 0.004 ? Math.min(255, acc[j + c] / n / a) : 0;
          img.data[j + 3] = 255 * a;
        }
      } else for (let j = 0; j < acc.length; j++) img.data[j] = acc[j] / n;
      g.putImageData(img, 0, 0);
      const blob = await new Promise((r) => c2.toBlob(r, 'image/png'));
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${ctx.name()}-${size}${alpha ? '-transparent' : ''}.png`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      stat.textContent = `Saved ${a.download} (${n} samples)`;
    } catch (e) {
      stat.textContent = `Could not render the still: ${e.message}`;
    } finally {
      st.setTransparent(false);
      st.hold = false;
      ctx.restore();
      rendering = false;
    }
  };
  return {enter, leave, get active() {
    return active;
  }};
}

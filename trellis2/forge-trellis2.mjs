/* FORGE TRELLIS.2 / GPT-6 — additive, static GLB viewer; does not replace Forge engines. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const BASE = "https://cdn.jsdelivr.net/npm/three@0.181.0/";
  const MAX_GLB_BYTES = 90 * 1024 * 1024;
  const state = { image: null, raw: null, name: "", active: false, runtime: null, renderer: null, controls: null, scene: null, camera: null, box: null, token: "", job: "", source: "", mixer: null, animationFrame: 0, resizeHandler: null };
  let view, statusEl, proxyEl, host, originalHost, controlsEl, dlBtn, pngBtn;
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  function status(msg, bad = false) {
    if (statusEl) { statusEl.textContent = msg; statusEl.style.color = bad ? "#ffb49e" : "#a7ebd0"; }
  }
  function inspectGLB(bytes) {
    if (!(bytes instanceof Uint8Array) || bytes.byteLength < 20) throw Error("GLB eksik veya boş");
    const d = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    if (d.getUint32(0, true) !== 0x46546c67 || d.getUint32(4, true) !== 2 || d.getUint32(8, true) !== bytes.byteLength) throw Error("Geçersiz glTF 2.0 GLB başlığı");
    let at = 12, json = null;
    while (at + 8 <= bytes.byteLength) {
      const len = d.getUint32(at, true), kind = d.getUint32(at + 4, true);
      if (at + 8 + len > bytes.byteLength) throw Error("GLB parçası sınır dışına taşıyor");
      if (kind === 0x4e4f534a) json = JSON.parse(new TextDecoder().decode(bytes.subarray(at + 8, at + 8 + len)).trim());
      at += 8 + len;
    }
    if (at !== bytes.byteLength || !json || json.asset?.version !== "2.0") throw Error("GLB JSON veya parça yapısı bozuk");
    if (!(json.meshes?.length > 0)) throw Error("GLB içinde 3D mesh yok");
    const unsupported = (json.extensionsRequired || []).filter(x => ["KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_texture_basisu"].includes(x));
    if (unsupported.length) throw Error("Bu sıkıştırılmış GLB türü için çözücü gerekli: " + unsupported.join(", "));
    return json;
  }
  function makeButton(label, fn) {
    const b = document.createElement("button"); b.type = "button"; b.className = "btn"; b.textContent = label; b.addEventListener("click", fn); return b;
  }
  function resetViewer() {
    state.active = false;
    if (state.animationFrame) cancelAnimationFrame(state.animationFrame);
    state.animationFrame = 0;
    state.mixer?.stopAllAction();
    if (state.resizeHandler) window.removeEventListener("resize", state.resizeHandler);
    state.resizeHandler = null;
    if (state.controls) state.controls.dispose();
    if (state.scene) state.scene.traverse(o => {
      if (o.isMesh) {
        o.geometry?.dispose();
        for (const mat of (Array.isArray(o.material) ? o.material : [o.material])) {
          if (!mat) continue;
          for (const key of ["map","normalMap","metalnessMap","roughnessMap","emissiveMap","aoMap","alphaMap"]) mat[key]?.dispose();
          mat.dispose();
        }
      }
    });
    state.renderer?.dispose();
    state.renderer?.forceContextLoss();
    if (view) { view.remove(); view = null; }
    if (controlsEl) { controlsEl.remove(); controlsEl = null; }
    if (originalHost) originalHost.style.display = "";
    state.scene = null; state.camera = null; state.controls = null; state.renderer = null; state.box = null;
    state.mixer = null; state.raw = null; state.name = "";
    const detail = $("s3-import-out"); if (detail) detail.textContent = "";
  }
  async function libraries() {
    if (state.runtime) return state.runtime;
    const [threeMod, loaderMod, orbitMod] = await Promise.all([
      import("three"),
      import(BASE + "examples/jsm/loaders/GLTFLoader.js"),
      import(BASE + "examples/jsm/controls/OrbitControls.js")
    ]);
    state.runtime = { THREE: threeMod, GLTFLoader: loaderMod.GLTFLoader, OrbitControls: orbitMod.OrbitControls };
    return state.runtime;
  }
  async function showGLB(bytes, name) {
    if (bytes.byteLength > MAX_GLB_BYTES) throw Error("GLB 90 MB sınırını aşıyor; telefon belleği korunuyor");
    const meta = inspectGLB(bytes);
    const { THREE, GLTFLoader, OrbitControls } = await libraries();
    const gltf = await new Promise((resolve, reject) => new GLTFLoader().parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), "", resolve, reject));
    let meshes = 0, tris = 0, uv = 0, textures = 0, materialCount = 0;
    gltf.scene.traverse(o => {
      if (!o.isMesh) return;
      meshes++;
      const p = o.geometry?.getAttribute("position");
      const idx = o.geometry?.getIndex();
      tris += idx ? idx.count / 3 : (p?.count || 0) / 3;
      if (o.geometry?.getAttribute("uv")) uv++;
      for (const m of (Array.isArray(o.material) ? o.material : [o.material])) {
        if (!m) continue;
        materialCount++;
        if (m.map || m.metalnessMap || m.roughnessMap || m.normalMap) textures++;
      }
    });
    if (!meshes) throw Error("GLB sahnesinde çizilebilir mesh yok");
    // Validate bounds before replacing a working viewer.
    const bounds = new THREE.Box3().setFromObject(gltf.scene);
    if (bounds.isEmpty()) throw Error("Mesh sınır kutusu hesaplanamadı");
    resetViewer();
    view = document.createElement("div"); view.id = "trellis-live-view"; view.style.cssText = "width:100%;min-height:180px;height:clamp(200px,54vh,440px);background:#0c1626;border:1px solid #3f5870;border-radius:10px;overflow:hidden;touch-action:none";
    originalHost.insertAdjacentElement("afterend", view);
    originalHost.style.display = "none";
    let renderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true, powerPreference: "low-power", preserveDrawingBuffer: true }); }
    catch (err) { resetViewer(); throw Error("WebGL2 önizleme açılamadı: " + (err?.message || err)); }
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.95;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setSize(Math.max(240, view.clientWidth), Math.max(180, view.clientHeight), false);
    renderer.domElement.style.cssText = "width:100%;height:100%;display:block;touch-action:none";
    view.appendChild(renderer.domElement);
    const scene = new THREE.Scene(); scene.background = new THREE.Color(0x0c1626);
    scene.add(gltf.scene);
    scene.add(new THREE.HemisphereLight(0xe5f2ff, 0x3e4758, 1.0));
    const key = new THREE.DirectionalLight(0xffffff, 1.8); key.position.set(3, 5, 7); scene.add(key);
    const fill = new THREE.DirectionalLight(0x93b7ff, 0.65); fill.position.set(-4, 2, -3); scene.add(fill);
    const center = bounds.getCenter(new THREE.Vector3()), radius = Math.max(bounds.getSize(new THREE.Vector3()).length() * 0.6, 0.2);
    const camera = new THREE.PerspectiveCamera(38, Math.max(240, view.clientWidth) / Math.max(180, view.clientHeight), 0.01, Math.max(100, radius * 80));
    camera.position.set(center.x, center.y + radius * 0.12, center.z + radius * 2.8);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(center); controls.enablePan = false; controls.minDistance = radius * 0.7; controls.maxDistance = radius * 12;
    const draw = () => {
      if (!state.active) return;
      const w = Math.max(240, view.clientWidth), h = Math.max(180, view.clientHeight);
      if (Math.abs(camera.aspect - w / h) > 0.001) { camera.aspect = w / h; camera.updateProjectionMatrix(); }
      if (renderer.domElement.width !== Math.round(w * renderer.getPixelRatio()) || renderer.domElement.height !== Math.round(h * renderer.getPixelRatio())) {
        renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
      }
      renderer.render(scene, camera);
    };
    state.raw = new Uint8Array(bytes); state.name = name || "trellis2_model.glb";
    state.active = true; state.scene = scene; state.renderer = renderer; state.camera = camera; state.controls = controls; state.box = { center, radius, draw };
    controls.addEventListener("change", draw);
    state.resizeHandler = draw;
    window.addEventListener("resize", draw, { passive: true });
    controls.update(); draw();
    controlsEl = document.createElement("div"); controlsEl.className = "row";
    controlsEl.style.cssText = "display:flex;flex-wrap:wrap;gap:5px;margin-top:6px";
    const angle = deg => { const rad = deg * Math.PI / 180; camera.position.set(center.x + Math.sin(rad) * radius * 2.8, center.y + radius * 0.12, center.z + Math.cos(rad) * radius * 2.8); controls.update(); draw(); };
    controlsEl.append(makeButton("Ön", () => angle(0)), makeButton("Yan", () => angle(90)), makeButton("Arka", () => angle(180)));
    // Play animation clips embedded in imported GLB; never bind them to Forge's 26-bone rig.
    const clips = (gltf.animations || []).filter(clip => clip.duration > 0);
    if (clips.length) {
      const mixer = new THREE.AnimationMixer(gltf.scene), clock = new THREE.Clock();
      state.mixer = mixer;
      mixer.clipAction(clips[0]).play();
      let playing = true;
      const playBtn = makeButton("Animasyonu durdur", () => {
        playing = !playing;
        playBtn.textContent = playing ? "Animasyonu durdur" : "Animasyonu oynat";
      });
      controlsEl.append(playBtn);
      const tick = () => {
        if (!state.active || state.mixer !== mixer) return;
        const delta = Math.min(clock.getDelta(), 0.05);
        if (playing && !document.hidden && !$("tab-model")?.hidden) {
          mixer.update(delta); draw();
        }
        state.animationFrame = requestAnimationFrame(tick);
      };
      state.animationFrame = requestAnimationFrame(tick);
    }
    controlsEl.append(makeButton("PNG kaydet", () => {
      draw(); renderer.domElement.toBlob(blob => { if (blob) downloadBlob(blob, "forge_3d_gorunum.png"); else status("PNG çıkarılamadı", true); }, "image/png");
    }));
    controlsEl.append(makeButton("3 görünüş PNG", () => {
      const original = camera.position.clone(), composite = document.createElement("canvas");
      const w = renderer.domElement.width, h = renderer.domElement.height;
      composite.width = w * 3; composite.height = h;
      const ctx = composite.getContext("2d");
      for (const [i, deg] of [0, 90, 180].entries()) {
        angle(deg); renderer.render(scene, camera);
        ctx.drawImage(renderer.domElement, w * i, 0, w, h);
        ctx.fillStyle = "#ffffff"; ctx.font = Math.max(13, Math.floor(w / 20)) + "px sans-serif";
        ctx.fillText(["Ön (+Z)", "Yan (+X)", "Arka (-Z)"][i], w * i + 10, 28);
      }
      camera.position.copy(original); controls.update(); draw();
      composite.toBlob(blob => { if (blob) downloadBlob(blob, "forge_on_yan_arka.png"); }, "image/png");
    }));
    controlsEl.append(makeButton("GLB indir", () => downloadBlob(new Blob([state.raw], {type:"model/gltf-binary"}), state.name)));
    controlsEl.append(makeButton("Forge karakterine dön", () => {resetViewer(); status("Forge önizlemesine dönüldü.");}));
    view.insertAdjacentElement("afterend", controlsEl);
    status("Gerçek GLB açıldı: " + meshes + " mesh, " + Math.floor(tris) + " üçgen, " + uv + " UV'li mesh, " + materialCount + " materyal; " + textures + " dokulu materyal. Orijinal GLB korunuyor.");
    const detail = $("s3-import-out");
    if (detail) detail.textContent = "glTF 2.0: " + (meta.nodes?.length || 0) + " düğüm, " + (meta.materials?.length || 0) + " materyal, " + (meta.images?.length || 0) + " görüntü, " + (meta.skins?.length || 0) + " iskelet.";
  }
  function downloadBlob(blob, name) {
    const a = document.createElement("a"), url = URL.createObjectURL(blob);
    a.href = url; a.download = (name || "model.glb").replace(/[^a-zA-Z0-9._-]/g, "_");
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 20000);
  }
  function safeProxy() {
    const s = proxyEl.value.trim().replace(/\/+$/, "");
    if (!/^https:\/\//i.test(s) && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(s)) throw Error("Sunucu HTTPS olmalı (yerel test için localhost HTTP kabul edilir)");
    try { localStorage.setItem("forge-trellis2-proxy-url", s); } catch (_) { /* file:// private mode */ }
    return s;
  }
  async function request(path, opts = {}) {
    const base = safeProxy();
    if (!state.token) state.token = window.prompt("Forge sunucu erişim anahtarı (HTML içinde kaydedilmez):") || "";
    if (!state.token) throw Error("Sunucu erişim anahtarı girilmedi");
    const headers = new Headers(opts.headers || {}); headers.set("X-Forge-Token", state.token);
    const resp = await fetch(base + path, { ...opts, headers, cache: "no-store" });
    if (!resp.ok) {
      let msg = resp.status + " " + resp.statusText;
      try { const e = await resp.json(); if (typeof e.detail === "string") msg = e.detail; } catch (_) {}
      if (resp.status === 401 || resp.status === 403) state.token = "";
      throw Error(msg);
    }
    return resp;
  }
  async function produce() {
    const image = state.image;
    if (!image) { status("Önce Görsel bölümünden PNG/JPG yükleyin.", true); return; }
    try {
      if (!/^image\/(png|jpeg|webp)$/.test(image.type)) throw Error("PNG/JPG/WEBP dışında kaynak kabul edilmiyor");
      if (image.size > 10 * 1024 * 1024) throw Error("Resim 10 MB üzeri");
      status("TRELLIS.2 isteği hazırlanıyor; ücretsiz GPU erişimi garanti değil.");
      const fd = new FormData(); fd.append("image", image, image.name);
      const result = await (await request("/api/jobs", {method:"POST",body:fd})).json();
      if (!result.id) throw Error("Sunucu iş kimliği göndermedi");
      state.job = result.id;
      let job, polls = 0;
      do {
        await sleep(3500);
        job = await (await request("/api/jobs/" + encodeURIComponent(result.id))).json();
        status("TRELLIS.2: " + (job.message || job.status || "işleniyor"));
        if (++polls > 180) throw Error("İstek zaman aşımına uğradı; sunucu durumunu kontrol edin");
      } while (job.status === "queued" || job.status === "running");
      if (job.status !== "done") throw Error(job.message || "Gerçek 3D üretimi tamamlanamadı");
      const bytes = new Uint8Array(await (await request("/api/jobs/" + encodeURIComponent(result.id) + "/glb")).arrayBuffer());
      await showGLB(bytes, "trellis2_" + result.id + ".glb");
    } catch (e) { status("Gerçek TRELLIS.2 üretilemedi: " + (e?.message || String(e)), true); }
  }
  function init() {
    originalHost = $("pv3d-host-model");
    const file = $("s3-verify-file"), model = $("tab-model");
    if (!originalHost || !file || !model) return;
    const area = document.createElement("div"); area.id = "trellis2-controls"; area.style.cssText = "border-top:1px solid #3f5870;margin:8px 0;padding:8px 0";
    const label = document.createElement("label"); label.textContent = "TRELLIS.2 bağlantı sunucusu (HTTPS)";
    proxyEl = document.createElement("input"); proxyEl.id = "trellis2-proxy"; proxyEl.type = "url"; proxyEl.placeholder = "https://forge-trellis-proxy.onrender.com"; proxyEl.autocomplete = "url"; proxyEl.style.cssText = "width:100%;box-sizing:border-box"; try { proxyEl.value = localStorage.getItem("forge-trellis2-proxy-url") || ""; } catch (_) { proxyEl.value = ""; }
    label.appendChild(proxyEl);
    const btn = makeButton("TRELLIS.2 ile gerçek 3D üret", produce); btn.id = "trellis2-run";
    statusEl = document.createElement("p"); statusEl.id = "trellis2-status"; statusEl.setAttribute("role", "status"); statusEl.style.cssText = "font-size:12px;overflow-wrap:anywhere";
    area.append(label, btn, statusEl);
    const ctrl = model.querySelector(".col-ctl");
    // Keep the real 3D action visible beside the source information, not below every setting.
    const sourceLine = ctrl?.querySelector("#s3-srcline");
    if (sourceLine) sourceLine.insertAdjacentElement("afterend", area);
    else (ctrl || model).appendChild(area);
    const capture = e => { const f = e.target.files?.[0]; if (f) state.image = f; };
    for (const id of ["importFile", "quickImageFile"]) $(id)?.addEventListener("change", capture, true);
    file.addEventListener("change", async e => {
      const f = e.target.files?.[0]; if (!f) return;
      e.stopImmediatePropagation();
      try {
        const bytes = new Uint8Array(await f.arrayBuffer()), meta = inspectGLB(bytes);
        if (meta.extras?.forge && meta.skins?.length) {
          resetViewer();
          await window.ForgeV12.importGLB(f);
        } else await showGLB(bytes, f.name);
      } catch (err) { status("GLB açılamadı: " + (err?.message || String(err)), true); }
      e.target.value = "";
    }, true);
    $("s3-glb-close")?.addEventListener("click", () => { if (state.active) resetViewer(); });
    status("GLB açma hazır. TRELLIS.2 üretimi için çalışan ücretsiz API aracısı gerekiyor.");
    window.ForgeTrellis2 = {inspectGLB, showGLB, resetViewer, get state() { return { active:state.active, hasImage:!!state.image, hasGLB:!!state.raw, job:state.job, cameraAspect:state.camera?.aspect ?? null, viewportAspect:state.renderer ? state.renderer.domElement.clientWidth / state.renderer.domElement.clientHeight : null, hasAnimation:!!state.mixer }; }};
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();

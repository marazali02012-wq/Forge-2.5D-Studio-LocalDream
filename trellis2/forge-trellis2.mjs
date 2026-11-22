/* FORGE TRELLIS.2 / GPT-6 — additive, static GLB viewer; does not replace Forge engines. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const BASE = "https://cdn.jsdelivr.net/npm/three@0.181.0/";
  const MAX_GLB_BYTES = 90 * 1024 * 1024;
  const GRADIO_JS_URL = "https://cdn.jsdelivr.net/npm/@gradio/client@2.7.0/dist/index.min.js";
  const HF_SPACE = "microsoft/TRELLIS.2";
  const SF3D_SPACE = "stabilityai/stable-fast-3d";
  const state = { image: null, raw: null, name: "", active: false, runtime: null, renderer: null, controls: null, scene: null, camera: null, box: null, token: "", job: "", source: "", generating: false, mixer: null, animationFrame: 0, resizeHandler: null };
  let view, statusEl, proxyEl, engineEl, hfTokenEl, sourceFileEl, generateBtn, diagnosticBtn, fallbackLink, originalHost, controlsEl;
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
    // Do not persist stale or invalid proxy addresses across app sessions.
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
  async function limitedGLBDownload(url) {
    const addr = new URL(url);
    if (addr.protocol !== "https:" ||
        !(addr.hostname === "huggingface.co" || addr.hostname.endsWith(".hf.space"))) {
      throw Error("Beklenmeyen GLB indirme adresi: Hugging Face kaynağı doğrulanamadı");
    }
    const response = await fetch(addr.href, {cache: "no-store"});
    if (!response.ok) throw Error("GLB indirme HTTP " + response.status);
    const declared = Number(response.headers.get("content-length") || 0);
    if (declared > MAX_GLB_BYTES) throw Error("GLB dosyası 90 MB üzeri; telefon belleği korunuyor");
    const reader = response.body?.getReader();
    if (!reader) {
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (bytes.byteLength > MAX_GLB_BYTES) throw Error("GLB 90 MB sınırını aştı");
      return bytes;
    }
    const chunks = []; let total = 0;
    try {
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        total += value.byteLength;
        if (total > MAX_GLB_BYTES) throw Error("GLB 90 MB sınırını aştı");
        chunks.push(value);
      }
    } finally { try {await reader.cancel();} catch (_) {} }
    const result = new Uint8Array(total); let offset = 0;
    for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
    return result;
  }
  function returnedFile(data) {
    const files = Array.isArray(data?.data) ? data.data : [];
    const file = [files[1], files[0]].find(v => v && typeof v === "object" &&
      (typeof v.url === "string" || typeof v.path === "string"));
    if (!file) throw Error("TRELLIS.2 GLB dosyası döndürmedi; GPU üretimi başarısız olabilir");
    return file.url || file.path;
  }
  async function connectOfficial(space = HF_SPACE) {
    let library;
    try { library = await import(GRADIO_JS_URL); }
    catch (err) { throw Error("Gradio istemcisi yüklenemedi (internet/CDN): " + String(err?.message || err)); }
    if (!library.Client?.connect || !library.handle_file) throw Error("Gradio istemcisi uyumsuz; API başlatılamıyor");
    // User may optionally use their own Hugging Face quota. Token is never
    // saved to HTML/localStorage or sent to our custom proxy.
    const hfToken = hfTokenEl?.value?.trim() || "";
    if (hfToken && !/^hf_[a-zA-Z0-9]{12,}$/.test(hfToken)) {
      throw Error("Hugging Face token biçimi geçersiz; hf_ ile başlamalı");
    }
    const app = await library.Client.connect(space, hfToken ? { token: hfToken } : undefined);
    return {app, handle_file:library.handle_file};
  }
  async function diagnoseOfficial() {
    if (state.generating) return;
    diagnosticBtn.disabled = true;
    try {
      const stable = engineEl.value === "sf3d";
      status((stable ? "Stable Fast 3D" : "TRELLIS.2") + " API bağlantısı kontrol ediliyor; GPU kullanılmaz…");
      const {app} = await connectOfficial(stable ? SF3D_SPACE : HF_SPACE);
      const api = await app.view_api();
      const names = Object.keys(api?.named_endpoints || {});
      const required = stable
        ? ["/requires_bg_remove", "/run_button"]
        : ["/start_session", "/preprocess_image", "/image_to_3d", "/extract_glb"];
      const missing = required.filter(endpoint => !names.includes(endpoint));
      if (missing.length) throw Error("Resmî API değişmiş; eksik: " + missing.join(", "));
      status("API bağlantısı doğrulandı. Üretim/ZeroGPU kotası test edilmedi.");
    } catch (err) {
      const raw = String(err?.message || err);
      status("Bağlantı başarısız: " + raw.slice(0, 300) + (/failed to fetch|network|cors/i.test(raw) ? " Ağ veya CORS engeli olabilir." : ""), true);
    } finally {
      diagnosticBtn.disabled = false;
    }
  }
  function hasTransparentPixels(file) {
    return new Promise((resolve, reject) => {
      const bmp = document.createElement("img"), url = URL.createObjectURL(file);
      bmp.onload = () => {
        const size = Math.min(128, Math.max(bmp.naturalWidth, bmp.naturalHeight));
        const c = document.createElement("canvas");
        c.width = size; c.height = size;
        const ctx = c.getContext("2d", {willReadFrequently:true});
        ctx.clearRect(0,0,size,size);
        ctx.drawImage(bmp,0,0,size,size);
        const data = ctx.getImageData(0,0,size,size).data;
        let alpha = false;
        for(let i=3;i<data.length;i+=4) if(data[i]<250){alpha=true;break;}
        URL.revokeObjectURL(url); resolve(alpha);
      };
      bmp.onerror = () => { URL.revokeObjectURL(url); reject(Error("Resim açılamadı")); };
      bmp.src = url;
    });
  }
  async function produceStableFast3D(image) {
    // The official Stable Fast 3D API uses a background state between upload and Run.
    // Do not fabricate a complete 360 model from opaque JPEG or silently remove detail.
    if (!(await hasTransparentPixels(image))) {
      throw Error("Stable Fast 3D için şeffaf arka planlı PNG/WEBP gerekiyor. JPEG ya da düz fonlu resmi önce arka planından ayırın.");
    }
    status("Stable Fast 3D bağlantısı kuruluyor…");
    const {app, handle_file} = await connectOfficial(SF3D_SPACE);
    status("Şeffaf karakter resmi işleniyor…");
    try {
      await app.predict("/requires_bg_remove", {image:handle_file(image), fr:0.85});
    } catch (err) {
      throw Error("SF3D görsel hazırlama (/requires_bg_remove): " + String(err?.message || err));
    }
    status("Stable Fast 3D görsel hazır. Gerçek mesh ve UV üretimi isteniyor…");
    let output;
    try {
      // Official SF3D Gradio config has 7 ordered inputs. The first is an
      // unnamed Button whose value MUST be "Run"; named-object API calls
      // omitted it and made server run_button(...) return None (Error).
      // Third input is server-owned gr.State; client uses same session_hash.
      output = await app.predict("/run_button", [
        "Run", handle_file(image), null, 0.85, "None", -1, 1024
      ]);
    } catch (err) {
      throw Error("SF3D mesh üretimi (/run_button): " + String(err?.message || err)
        + ". Resmî web demosu çalışabilir; 'Resmî 3D demosunu aç' seçeneğini kullanabilirsiniz.");
    }
    const url = returnedFile(output);
    status("Gerçek Stable Fast 3D GLB alınıyor…");
    const bytes = await limitedGLBDownload(url);
    const metadata = inspectGLB(bytes);
    const textured = metadata.meshes?.some(mesh => (mesh.primitives||[]).some(p => {
      const mat = metadata.materials?.[p.material];
      return Number.isInteger(mat?.pbrMetallicRoughness?.baseColorTexture?.index)
        && Number.isInteger(p?.attributes?.TEXCOORD_0);
    }));
    if (!textured) throw Error("Stable Fast 3D geometri döndürdü fakat UV'li kaplama bulunamadı; eksik sonucu başarı saymıyoruz");
    await showGLB(bytes, "stable_fast_3d_model.glb");
  }
  async function produceDirect(image) {
    status("Resmî TRELLIS.2 ZeroGPU sunucusuna bağlanılıyor…");
    const {app, handle_file} = await connectOfficial();
    await app.predict("/start_session", {});
    status("Kaynak resim hazırlanıyor…");
    const processed = await app.predict("/preprocess_image", {input: handle_file(image)});
    const result = processed?.data?.[0];
    if (!result || typeof result !== "object" || !(result.url || result.path)) {
      throw Error("TRELLIS.2 hazırlanmış resim döndürmedi");
    }
    status("Gerçek 3D geometri/kaplama üretiliyor; ZeroGPU kotası ve sıra beklenebilir…");
    await app.predict("/image_to_3d", {
      image: handle_file(result.url || result.path), seed: 0, resolution: "1024",
      ss_guidance_strength: 7.5, ss_guidance_rescale: 0.7,
      ss_sampling_steps: 12, ss_rescale_t: 5.0,
      shape_slat_guidance_strength: 7.5, shape_slat_guidance_rescale: 0.5,
      shape_slat_sampling_steps: 12, shape_slat_rescale_t: 3.0,
      tex_slat_guidance_strength: 1.0, tex_slat_guidance_rescale: 0.0,
      tex_slat_sampling_steps: 12, tex_slat_rescale_t: 3.0
    });
    status("Geometri tamamlandı; kaplamalı GLB dışa aktarılıyor…");
    const extracted = await app.predict("/extract_glb", {decimation_target: 200000, texture_size: 2048});
    const url = returnedFile(extracted);
    status("Gerçek GLB indiriliyor ve doğrulanıyor…");
    const bytes = await limitedGLBDownload(url);
    await showGLB(bytes, "trellis2_gercek_model.glb");
  }
  async function produce() {
    if (state.generating) return;
    const image = state.image;
    if (!image) { status("Önce 3D kaynak resmi seçin (PNG/JPG/WEBP).", true); return; }
    state.generating = true;
    if (generateBtn) generateBtn.disabled = true;
    try {
      if (!/^image\/(png|jpeg|webp)$/.test(image.type)) throw Error("PNG/JPG/WEBP dışında kaynak kabul edilmiyor");
      if (image.size > 10 * 1024 * 1024) throw Error("Resim 10 MB üzeri");
      const stable = engineEl.value === "sf3d";
      const customServer = proxyEl?.value?.trim();
      if (stable && customServer) throw Error("Özel proxy yalnızca TRELLIS.2 için kullanılabilir; Stable Fast 3D'de sunucu alanını boş bırakın");
      if (stable) {
        await produceStableFast3D(image);
      } else if (!customServer) {
        await produceDirect(image);
      } else {
        status("Özel TRELLIS.2 sunucusuna bağlanılıyor…");
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
        const response = await request("/api/jobs/" + encodeURIComponent(result.id) + "/glb");
        const len = Number(response.headers.get("content-length") || 0);
        if (len > MAX_GLB_BYTES) throw Error("GLB dosyası 90 MB sınırını aşıyor");
        const bytes = new Uint8Array(await response.arrayBuffer());
        await showGLB(bytes, "trellis2_" + result.id + ".glb");
      }
    } catch (e) {
      const msg = String(e?.message || e);
      const quota = msg.match(/(\d+)s requested vs\. (\d+)s left/i);
      const hint = quota
        ? " Ücretsiz GPU kotası yetersiz: işlem " + quota[1] + " sn, kalan " + quota[2]
          + " sn. Kotanın yenilenmesini bekleyin veya kendi HF hesabınızın tokenıyla deneyin."
        : /quota|zero.?gpu|rate.?limit|too many|gpu|429/i.test(msg)
          ? " Ücretsiz GPU kotası veya sırası engel olabilir."
          : /failed to fetch|network|cors/i.test(msg)
            ? " Bağlantı veya tarayıcı CORS engelini kontrol edin." : "";
      status((engineEl.value === "sf3d" ? "Stable Fast 3D" : "TRELLIS.2") + " tamamlanamadı: "
        + (quota ? "GPU kotası engeli." : msg.slice(0, 280)) + hint, true);
    } finally {
      state.generating = false;
      if (generateBtn) generateBtn.disabled = false;
    }
  }
  function init() {
    originalHost = $("pv3d-host-model");
    const file = $("s3-verify-file"), model = $("tab-model");
    if (!originalHost || !file || !model) return;
    const area = document.createElement("div"); area.id = "trellis2-controls"; area.style.cssText = "border-top:1px solid #3f5870;margin:8px 0;padding:8px 0";
    const fileLabel = document.createElement("label");
    fileLabel.textContent = "3D kaynak resmi (PNG/JPG/WEBP)";
    sourceFileEl = document.createElement("input");
    sourceFileEl.id = "trellis2-image";
    sourceFileEl.type = "file";
    sourceFileEl.accept = "image/png,image/jpeg,image/webp";
    sourceFileEl.style.cssText = "width:100%;max-width:100%;box-sizing:border-box";
    sourceFileEl.addEventListener("change", e => {
      const f = e.target.files?.[0];
      if (f) { state.image = f; status("Kaynak resim seçildi: " + f.name); }
    });
    fileLabel.appendChild(sourceFileEl);
    const engineLabel = document.createElement("label");
    engineLabel.textContent = "Gerçek 3D üretim motoru";
    engineEl = document.createElement("select");
    engineEl.id = "trellis2-engine";
    engineEl.style.cssText = "width:100%;box-sizing:border-box;margin-top:5px";
    for (const [value, title] of [
      ["sf3d", "Stable Fast 3D — çalışan alternatif, UV GLB"],
      ["trellis2", "Microsoft TRELLIS.2 — deneyseldir"]
    ]) {
      const option = document.createElement("option"); option.value=value; option.textContent=title;
      engineEl.append(option);
    }
    engineEl.value = "sf3d";
    engineEl.addEventListener("change", () => {
      if (proxyEl) { proxyEl.value = ""; }
      if (fallbackLink) fallbackLink.hidden = engineEl.value !== "sf3d";
      status(engineEl.value === "sf3d"
        ? "Stable Fast 3D: şeffaf PNG/WEBP kullanın. Ücretsiz GPU kotası garanti değil."
        : "TRELLIS.2: resmî GPU üretimi hata verdi; bu motor deneysel.");
    });
    engineLabel.appendChild(engineEl);
    const hfDetails = document.createElement("details");
    hfDetails.className = "acc";
    const hfSummary = document.createElement("summary");
    hfSummary.textContent = "Ücretsiz GPU kotası için HF hesabı (isteğe bağlı)";
    const hfLabel = document.createElement("label");
    hfLabel.textContent = "Hugging Face erişim tokenı — yalnızca bu oturum; kaydedilmez";
    hfTokenEl = document.createElement("input");
    hfTokenEl.id = "sf3d-hf-token";
    hfTokenEl.type = "password";
    hfTokenEl.autocomplete = "off";
    hfTokenEl.placeholder = "hf_…";
    hfTokenEl.style.cssText = "width:100%;box-sizing:border-box";
    hfLabel.appendChild(hfTokenEl);
    const hfLink = document.createElement("a");
    hfLink.href = "https://huggingface.co/settings/tokens";
    hfLink.target = "_blank";
    hfLink.rel = "noopener noreferrer";
    hfLink.textContent = "Hugging Face hesabında token oluştur";
    hfLink.style.cssText = "display:inline-block;font-size:12px;color:#b3e1ff;text-decoration:underline";
    hfDetails.append(hfSummary,hfLabel,hfLink);
    const advanced = document.createElement("details");
    advanced.className = "acc";
    const summary = document.createElement("summary");
    summary.textContent = "Özel sunucu (isteğe bağlı)";
    const label = document.createElement("label"); label.textContent = "Yalnızca kendi TRELLIS.2 proxy sunucun varsa HTTPS adresini gir";
    proxyEl = document.createElement("input"); proxyEl.id = "trellis2-proxy"; proxyEl.type = "url"; proxyEl.placeholder = "https://your-own-proxy.example"; proxyEl.autocomplete = "off"; proxyEl.style.cssText = "width:100%;box-sizing:border-box"; proxyEl.value = "";
    label.appendChild(proxyEl);
    const btn = makeButton("Seçili motorla gerçek 3D üret", produce); btn.id = "trellis2-run";
    generateBtn = btn;
    diagnosticBtn = makeButton("API bağlantısını kontrol et", diagnoseOfficial);
    diagnosticBtn.id = "trellis2-diagnostic";
    fallbackLink = document.createElement("a");
    fallbackLink.id = "sf3d-official-fallback";
    fallbackLink.href = "https://huggingface.co/spaces/stabilityai/stable-fast-3d";
    fallbackLink.target = "_blank";
    fallbackLink.rel = "noopener noreferrer";
    fallbackLink.textContent = "Resmî 3D demosunu aç — GLB indirip Forge'a yükle";
    fallbackLink.style.cssText = "display:inline-block;margin-top:5px;font-size:12px;color:#b3e1ff;text-decoration:underline";
    statusEl = document.createElement("p"); statusEl.id = "trellis2-status"; statusEl.setAttribute("role", "status"); statusEl.style.cssText = "font-size:12px;overflow-wrap:anywhere";
    advanced.append(summary, label);
    area.append(engineLabel, fileLabel, btn, diagnosticBtn, fallbackLink, hfDetails, advanced, statusEl);
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
    status("Stable Fast 3D seçili. Şeffaf PNG/WEBP yükleyin; GPU erişimi ücretsiz demoda değişebilir.");
    window.ForgeTrellis2 = {inspectGLB, showGLB, resetViewer, get state() { return { active:state.active, hasImage:!!state.image, hasGLB:!!state.raw, generating:state.generating, engine:engineEl?.value, job:state.job, cameraAspect:state.camera?.aspect ?? null, viewportAspect:state.renderer ? state.renderer.domElement.clientWidth / state.renderer.domElement.clientHeight : null, hasAnimation:!!state.mixer }; }};
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();

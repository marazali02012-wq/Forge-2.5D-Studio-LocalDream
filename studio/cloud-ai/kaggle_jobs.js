const kaggleDialog = $('forgeKaggleDialog');
const kaggleStatus = $('forgeKaggleStatus');
const kaggleStart = $('forgeKaggleStart');
const kaggleOpenModel = $('forgeKaggleOpenModel');
let pendingKaggleModel = null;

function openKaggleModel() {
  if (!pendingKaggleModel) return;
  kaggleDialog.close();
  if (showForgeAI(pendingKaggleModel)) {
    pendingKaggleModel = null;
    kaggleOpenModel.hidden = true;
  }
}

$('forgeKaggleOpen').onclick = () => {
  aiTools.close();
  kaggleDialog.showModal();
};
$('forgeKaggleClose').onclick = () => kaggleDialog.close();
kaggleOpenModel.onclick = openKaggleModel;

kaggleStart.onclick = async () => {
  const image = $('forgeKaggleImage').files[0];
  if (!image || !['image/png', 'image/jpeg', 'image/webp'].includes(image.type)
      || !image.size || image.size > 5 * 1024 * 1024) {
    kaggleStatus.textContent = 'En fazla 5 MiB boyutunda bir PNG, JPEG veya WebP seç.';
    return;
  }
  let url;
  try {
    url = new URL($('forgeKaggleServer').value.trim());
    if (url.username || url.password || url.search || url.hash || url.pathname !== '/' ||
        !(url.protocol === 'https:' ||
          (url.protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(url.hostname)))) {
      throw Error();
    }
  } catch {
    kaggleStatus.textContent = 'Forge sunucusunun HTTPS kök adresini gir.';
    return;
  }
  const tokenInput = $('forgeKaggleAccess');
  const token = tokenInput.value;
  if (!token) {
    kaggleStatus.textContent = 'Forge erişim anahtarını gir.';
    return;
  }
  if (!confirm('Görseli Forge üzerinden özel Kaggle veri kümesine yükleyip 3D üretim başlat?')) return;
  tokenInput.value = '';
  pendingKaggleModel = null;
  kaggleOpenModel.hidden = true;
  kaggleStart.disabled = true;
  kaggleStatus.textContent = 'İş kaydediliyor…';

  async function request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 75000);
    try {
      const response = await fetch(url.origin + path, {
        ...options, headers: {...options.headers, Authorization: 'Bearer ' + token},
        signal: controller.signal, redirect: 'error', cache: 'no-store', credentials: 'omit',
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw Error(typeof detail.error === 'string' ? detail.error : 'Forge HTTP ' + response.status);
      }
      if (!path.endsWith('/model')) return await response.json();
      const length = Number(response.headers.get('Content-Length'));
      if (response.headers.get('Content-Type') !== 'model/gltf-binary'
          || !Number.isInteger(length) || length < 28 || length > 8e6) {
        throw Error('Sunucu geçerli boyutta GLB göndermedi.');
      }
      const buffer = await response.arrayBuffer();
      if (buffer.byteLength !== length) throw Error('GLB eksik indirildi.');
      return buffer;
    } finally {
      clearTimeout(timer);
    }
  }

  try {
    const jobsPath = '/v1/kaggle-jobs';
    let job = await request(jobsPath, {
      method: 'POST', headers: {'Content-Type': image.type}, body: image,
    });
    if (!/^[0-9a-f]{64}$/.test(job.id)) throw Error('İş kimliği geçersiz.');
    const jobPath = jobsPath + '/' + job.id;
    const deadline = Date.now() + 3 * 3600_000;
    while (true) {
      kaggleStatus.textContent = job.message;
      if (job.status === 'ready') {
        // TripoSG follows the standard GLB import orientation.
        pendingKaggleModel = parseForgeAiGLB(await request(jobPath + '/model'));
        kaggleOpenModel.hidden = false;
        kaggleStatus.textContent = 'GLB hazır. Editörde açabilirsin.';
        if (kaggleDialog.open) openKaggleModel();
        break;
      }
      if (['error', 'cancelled', 'timed_out'].includes(job.status)) break;
      if (Date.now() >= deadline) {
        kaggleStatus.textContent = 'Bekleme süresi doldu. Aynı görsel ile mevcut işi tekrar kontrol et.';
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 15000));
      job = await request(jobPath);
    }
  } catch (error) {
    kaggleStatus.textContent = error.name === 'AbortError'
      ? 'Bağlantı zaman aşımına uğradı. Aynı görsel ile mevcut işi tekrar kontrol et.'
      : error.message;
  } finally {
    kaggleStart.disabled = false;
  }
};

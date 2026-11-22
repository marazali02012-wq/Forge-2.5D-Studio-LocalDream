"""Browser regression: no-proxy TRELLIS.2 API pipeline, mocked upstream (NOT real GPU generation)."""
from pathlib import Path
import os
from PIL import Image
from playwright.sync_api import sync_playwright
from trellis2.test_fixture import glb

root = Path(__file__).resolve().parent.parent
html = root / "Forge_25D_V14_1_TRELLIS2_GPT6.html"
output = root / "test-sonuclari" / "trellis2"
output.mkdir(parents=True, exist_ok=True)
image_path = output / "direct_source.png"
im = Image.new("RGBA", (128, 128), (0,0,0,0))
from PIL import ImageDraw
ImageDraw.Draw(im).ellipse((32,18,96,110), fill=(150,60,10,255))
im.save(image_path)
fixture = glb(webp=True)

MOCK_CLIENT = """
export const handle_file = x => ({ file: x });
export const Client = {connect: async(space, options) => {
  window.__hfLastAuth = options?.token || "";
  if(!['microsoft/TRELLIS.2','stabilityai/stable-fast-3d'].includes(space)) throw Error('Incorrect Space');
  window.__hfCalls = [];
  window.__hfSpace = space;
  return {view_api: async () => ({named_endpoints:Object.fromEntries(
    (space === 'stabilityai/stable-fast-3d'
    ? ['/requires_bg_remove','/run_button']
    : ['/start_session','/preprocess_image','/image_to_3d','/extract_glb']).map(x=>[x,{}]))}),
    predict: async(endpoint, args) => {
    window.__hfCalls.push({endpoint, args});
    if (window.__testRemoteError && endpoint === '/image_to_3d') throw Error('ZeroGPU quota exhausted');
    if(endpoint === '/requires_bg_remove') return {data:[{url:'https://stabilityai-stable-fast-3d.hf.space/bg.png'},null]};
    if(endpoint === '/run_button') return {data:[{url:'https://stabilityai-stable-fast-3d.hf.space/processed.png'}, {url:'https://stabilityai-stable-fast-3d.hf.space/model.glb'}]};
    if(endpoint === '/start_session') return {data:[]};
    if(endpoint === '/preprocess_image') return {data:[{url:'https://microsoft-trellis-2.hf.space/mock_processed.png'}]};
    if(endpoint === '/image_to_3d') return {data:['mock 3D output']};
    if(endpoint === '/extract_glb') return {data:[{url:'https://microsoft-trellis-2.hf.space/model.glb'}, {url:'https://microsoft-trellis-2.hf.space/model.glb'}]};
    throw Error('Unexpected endpoint '+endpoint);
  }};
}};
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True, args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
        **({"executable_path": os.environ["FORGE_CHROMIUM"]} if os.environ.get("FORGE_CHROMIUM") else {})
    )
    page = browser.new_page(viewport={"width": 390, "height": 844}, accept_downloads=True)
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.route("https://cdn.jsdelivr.net/npm/@gradio/client@2.7.0/dist/index.min.js",
        lambda route: route.fulfill(status=200, content_type="application/javascript", body=MOCK_CLIENT,
            headers={"Access-Control-Allow-Origin": "*"}))
    page.route("https://microsoft-trellis-2.hf.space/model.glb",
        lambda route: route.fulfill(status=200, content_type="model/gltf-binary", body=fixture,
            headers={"Access-Control-Allow-Origin": "*", "Content-Length": str(len(fixture))}))
    page.route("https://stabilityai-stable-fast-3d.hf.space/model.glb",
        lambda route: route.fulfill(status=200, content_type="model/gltf-binary", body=fixture,
            headers={"Access-Control-Allow-Origin":"*","Content-Length":str(len(fixture))}))
    page.goto(html.as_uri(), wait_until="domcontentloaded")
    page.wait_for_function("!!window.ForgeV12 && !!window.ForgeTrellis2 && !!window.ForgeV11?.ready", timeout=60000)
    page.evaluate("ForgeShell.go('model')")
    assert page.locator("#trellis2-image").count() == 1
    assert page.locator("#trellis2-proxy").input_value() == ""
    assert page.locator("#trellis2-engine").input_value() == "sf3d"
    assert page.locator("#sf3d-hf-token").get_attribute("type") == "password"
    page.locator("#sf3d-hf-token").fill("hf_ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    page.locator("#trellis2-diagnostic").click()
    page.wait_for_function("document.querySelector('#trellis2-status').textContent.includes('API bağlantısı doğrulandı')",timeout=30000)
    assert page.evaluate("window.__hfLastAuth") == "hf_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    page.locator("#sf3d-hf-token").fill("")
    assert page.locator("#sf3d-official-fallback").get_attribute("href") == "https://huggingface.co/spaces/stabilityai/stable-fast-3d"
    page.locator("#trellis2-engine").select_option("trellis2")
    page.locator("#trellis2-diagnostic").click()
    page.wait_for_function("document.querySelector('#trellis2-status').textContent.includes('API bağlantısı doğrulandı')",timeout=30000)
    assert "Üretim/ZeroGPU kotası test edilmedi" in page.locator("#trellis2-status").inner_text()
    page.locator("#trellis2-run").click()
    assert "kaynak resmi seçin" in page.locator("#trellis2-status").inner_text().lower()
    page.locator("#trellis2-image").set_input_files(str(image_path))
    page.evaluate("window.__testRemoteError = true")
    page.locator("#trellis2-run").click()
    page.wait_for_function("document.querySelector('#trellis2-status').textContent.includes('ZeroGPU quota exhausted')", timeout=30000)
    assert not page.evaluate("ForgeTrellis2.state.active")
    assert not page.evaluate("ForgeTrellis2.state.generating")
    assert page.locator("#trellis2-run").is_enabled()
    assert [x["endpoint"] for x in page.evaluate("window.__hfCalls")] == [
        "/start_session", "/preprocess_image", "/image_to_3d"]
    print("PASS direct HF mocked API quota error: no fake GLB")
    page.evaluate("window.__testRemoteError = false")
    page.locator("#trellis2-run").click()
    page.wait_for_function("ForgeTrellis2.state.active", timeout=90000)
    assert page.locator("#trellis-live-view canvas").count() == 1
    assert [x["endpoint"] for x in page.evaluate("window.__hfCalls")] == [
        "/start_session", "/preprocess_image", "/image_to_3d", "/extract_glb"]
    args = page.evaluate("window.__hfCalls.find(x=>x.endpoint==='/image_to_3d').args")
    assert args["resolution"] == "1024"
    export = page.evaluate("window.__hfCalls.find(x=>x.endpoint==='/extract_glb').args")
    assert export == {"decimation_target": 200000, "texture_size": 2048}
    with page.expect_download(timeout=15000) as dl:
        page.get_by_role("button", name="GLB indir", exact=True).click()
    result = output / "direct_mock_glb.glb"
    dl.value.save_as(result)
    assert result.read_bytes() == fixture

    # Independent engine from a real, currently working public demo, mocked in CI.
    page.get_by_role("button", name="Forge karakterine dön", exact=True).click()
    page.locator("#trellis2-engine").select_option("sf3d")
    page.locator("#trellis2-image").set_input_files(str(image_path))
    page.locator("#trellis2-diagnostic").click()
    page.wait_for_function("document.querySelector('#trellis2-status').textContent.includes('API bağlantısı doğrulandı')",timeout=30000)
    page.locator("#trellis2-run").click()
    page.wait_for_function("ForgeTrellis2.state.active", timeout=90000)
    assert page.evaluate("ForgeTrellis2.state.engine === 'sf3d'")
    assert [x["endpoint"] for x in page.evaluate("window.__hfCalls")] == ["/requires_bg_remove", "/run_button"]
    stable_args=page.evaluate("window.__hfCalls.find(x=>x.endpoint==='/run_button').args")
    assert isinstance(stable_args,list),stable_args
    assert stable_args[0] == "Run",stable_args
    assert stable_args[3] == 0.85 and stable_args[4] == "None" and stable_args[6] == 1024,stable_args
    assert "2 mesh" in page.locator("#trellis2-status").inner_text()
    with page.expect_download(timeout=15000) as stable_download:
        page.get_by_role("button", name="GLB indir", exact=True).click()
    stable_out = output / "stable_fast_3d_mock.glb"
    stable_download.value.save_as(stable_out)
    assert stable_out.read_bytes()==fixture
    assert not errors, errors
    print("PASS direct HF mocked API: PNG->preprocess->3D->GLB->viewer->lossless download")
    browser.close()

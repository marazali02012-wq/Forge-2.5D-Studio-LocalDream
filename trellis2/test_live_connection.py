"""Live Gradio CDN/API connectivity probe only: NO GPU work, NO 3D generation."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent.parent
report = root / "test-sonuclari" / "trellis2" / "gercek_api_baglanti.json"
report.parent.mkdir(parents=True, exist_ok=True)
outcome = {
    "test": "real_jsdelivr_gradio_and_official_api_connectivity",
    "gpu_generation_tested": False,
    "glb_generated": False,
    "api_connected": False,
}
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
            **({"executable_path": os.environ["FORGE_CHROMIUM"]} if os.environ.get("FORGE_CHROMIUM") else {})
        )
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto((root / "Forge_25D_V14_1_TRELLIS2_GPT6.html").as_uri(),
                      wait_until="domcontentloaded", timeout=25000)
            result = page.evaluate("""async () => {
              const guard = new Promise((_, reject) => setTimeout(() => reject(new Error('25s API connection timeout')), 25000));
              const run = async () => {
                const library = await import('https://cdn.jsdelivr.net/npm/@gradio/client@2.7.0/dist/index.min.js');
                if (!library.Client?.connect || !library.handle_file) throw Error('Gradio CDN module exports missing');
                const app = await library.Client.connect('microsoft/TRELLIS.2');
                const api = await app.view_api();
                const required = ['/start_session', '/preprocess_image', '/image_to_3d', '/extract_glb'];
                const names = Object.keys(api?.named_endpoints || {});
                const missing = required.filter(x => !names.includes(x));
                if (missing.length) throw Error('API missing endpoints: ' + missing.join(', '));
                return {available_endpoints: required};
              };
              return await Promise.race([run(), guard]);
            }""")
            outcome["api_connected"] = True
            outcome.update(result)
        finally:
            browser.close()
except Exception as exc:
    outcome["error"] = (str(exc) or repr(exc))[:1000]
finally:
    report.write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8")
    print("LIVE API CONNECTION (no GPU):", json.dumps(outcome, ensure_ascii=False))
if not outcome["api_connected"]:
    raise SystemExit("Official Gradio CDN/API connection failed; no 3D generation was attempted")

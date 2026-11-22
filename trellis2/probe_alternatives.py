"""Probe independent 3D provider APIs in a real Chrome browser, without GPU generation.
Every engine is a separate outcome. 404/quota aren't misreported as success.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent.parent
output = root / "test-sonuclari" / "trellis2" / "alternative_api_matrix.json"
output.parent.mkdir(parents=True, exist_ok=True)
providers = [
  ("stable_fast_3d", "stabilityai/stable-fast-3d"),
  ("hunyuan3d_2", "tencent/Hunyuan3D-2"),
  ("hunyuan3d_2_1", "tencent/Hunyuan3D-2.1"),
  ("triposr", "stabilityai/TripoSR"),
]
matrix = {"gpu_generation_tested": False, "models_generated": 0, "providers": []}
with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
        **({"executable_path": os.environ["FORGE_CHROMIUM"]} if os.environ.get("FORGE_CHROMIUM") else {})
    )
    page = browser.new_page()
    page.goto((root / "Forge_25D_V14_1_TRELLIS2_GPT6.html").as_uri(), wait_until="domcontentloaded")
    for ident, space in providers:
        try:
            result = page.evaluate("""async space => {
                const timeout = new Promise((_,rej) => setTimeout(() => rej(Error('15s connection timeout')), 15000));
                const test = async () => {
                    const {Client} = await import('https://cdn.jsdelivr.net/npm/@gradio/client@2.7.0/dist/index.min.js');
                    const client = await Client.connect(space);
                    const schema = await client.view_api();
                    const endpoints = Object.entries(schema?.named_endpoints || {}).map(([name, spec]) => ({
                        name,
                        params: (spec.parameters || []).map(x => ({
                          name: x.parameter_name,
                          default: x.parameter_default,
                          component: x.component
                        })),
                        returns: (spec.returns || []).map(x => x.component)
                    }));
                    if (!endpoints.length) throw Error('API connected but no public named endpoints');
                    return {connected: true, endpoints};
                };
                return Promise.race([test(), timeout]);
            }""", space)
            matrix["providers"].append({"engine": ident, "space": space, **result})
        except Exception as exc:
            matrix["providers"].append({
                "engine": ident, "space": space, "connected": False,
                "error": (str(exc) or repr(exc))[:600]
            })
        print("ALTERNATIVE API",json.dumps(matrix["providers"][-1],ensure_ascii=False))
    browser.close()
output.write_text(json.dumps(matrix, ensure_ascii=False, indent=2),encoding="utf-8")
print("NO GPU JOBS WERE CALLED. NO REAL 3D MODELS WERE GENERATED.")

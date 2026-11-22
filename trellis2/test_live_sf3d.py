"""End-to-end real Stable Fast 3D GPU run through Forge HTML, not a synthetic fixture.

Uses official public Stability AI demo source art; generated files are test evidence,
not licensed game art. Never claim success unless downloaded GLB contains UV + texture.
"""
from __future__ import annotations
import json
import os
import time
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "test-sonuclari" / "trellis2"
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = OUT / "stable_fast_real_source.png"
REPORT = OUT / "stable_fast_real_generation.json"
EXAMPLE_URLS = [
    "https://raw.githubusercontent.com/Stability-AI/stable-fast-3d/main/demo_files/examples/otter_samurai.png",
    "https://raw.githubusercontent.com/Stability-AI/stable-fast-3d/main/demo_files/examples/character1.png",
]
report = {
    "kind": "REAL_GPU_IMAGE_TO_3D_ATTEMPT",
    "provider": "stabilityai/stable-fast-3d",
    "source_is_public_example": True,
    "uses_mock": False,
    "gpu_generation_confirmed": False,
    "glb_downloaded": False,
    "uv_textured": False,
}

def save():
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("REAL SF3D:", json.dumps(report, ensure_ascii=False), flush=True)

try:
    for url in EXAMPLE_URLS:
        try:
            with urllib.request.urlopen(url, timeout=25) as response:
                SOURCE.write_bytes(response.read(3 * 1024 * 1024))
            with Image.open(SOURCE) as im:
                a = im.convert("RGBA").getchannel("A")
                if a.getextrema()[0] == 255:
                    raise ValueError("sample has no transparent pixels")
                report["source_url"] = url
                report["source_size"] = list(im.size)
            break
        except Exception as exc:
            report.setdefault("download_attempts", []).append(str(exc)[:120])
    else:
        raise RuntimeError("No official transparent sample could be downloaded")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
            **({"executable_path": os.environ["FORGE_CHROMIUM"]} if os.environ.get("FORGE_CHROMIUM") else {})
        )
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844}, accept_downloads=True)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto((ROOT / "Forge_25D_V14_1_TRELLIS2_GPT6.html").as_uri(),
                      wait_until="domcontentloaded", timeout=25000)
            page.wait_for_function("!!window.ForgeV12 && !!window.ForgeTrellis2 && !!window.ForgeV11?.ready", timeout=60000)
            page.evaluate("ForgeShell.go('model')")
            assert page.locator("#trellis2-engine").input_value() == "sf3d"
            page.locator("#trellis2-image").set_input_files(str(SOURCE))
            page.locator("#trellis2-run").click()
            deadline = time.monotonic() + 210
            status = ""
            while time.monotonic() < deadline:
                page.wait_for_timeout(2000)
                status = page.locator("#trellis2-status").inner_text()
                if page.evaluate("ForgeTrellis2.state.active") or ("tamamlanamadı" in status):
                    break
            report["ui_status"] = status[:1000]
            report["browser_errors"] = errors[:10]
            if not page.evaluate("ForgeTrellis2.state.active"):
                report["error"] = "No valid 3D viewer after GPU request"
                raise RuntimeError("Real Stable Fast 3D generation did not reach an active viewer: " + status[:350])
            report["gpu_generation_confirmed"] = True
            # Screenshot evidence: real model, not a mock fixture.
            page.screenshot(path=str(OUT / "stable_fast_REAL_viewer.png"))
            with page.expect_download(timeout=25000) as dl:
                page.get_by_role("button", name="GLB indir", exact=True).click()
            glb_file = OUT / "stable_fast_REAL_textured.glb"
            dl.value.save_as(glb_file)
            report["glb_downloaded"] = True
            report["glb_size_bytes"] = glb_file.stat().st_size
            # Validate GLB in Python without loading huge binary into browser JS.
            import struct
            data = glb_file.read_bytes()
            assert data[:4] == b"glTF"
            assert struct.unpack_from("<I", data, 8)[0] == len(data)
            length = struct.unpack_from("<I", data, 12)[0]
            meta = json.loads(data[20:20 + length].decode())
            valid = any(
                "TEXCOORD_0" in p.get("attributes", {})
                and isinstance(
                    (meta.get("materials", []) + [{}])[p.get("material", len(meta.get("materials", [])))]
                    .get("pbrMetallicRoughness", {}).get("baseColorTexture", {}).get("index"), int)
                for mesh in meta.get("meshes", []) for p in mesh.get("primitives", [])
                if isinstance(p.get("material"), int)
                and 0 <= p.get("material") < len(meta.get("materials", []))
            )
            report["uv_textured"] = bool(valid)
            report["meshes"] = len(meta.get("meshes", []))
            report["texture_images"] = len(meta.get("images", []))
            if not valid:
                raise AssertionError("Generated GLB has no UV-mapped PBR base texture")
        finally:
            browser.close()
except Exception as exc:
    report["error"] = str(exc)[:850]
finally:
    save()

if not all(report[k] for k in ["gpu_generation_confirmed", "glb_downloaded", "uv_textured"]):
    raise SystemExit(1)

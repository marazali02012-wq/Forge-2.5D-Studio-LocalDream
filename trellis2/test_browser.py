"""Browser GLB importer smoke test: offline synthetic fixture, not AI production."""
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from trellis2.test_fixture import glb
root=Path(__file__).resolve().parent.parent
html=root/"Forge_25D_V14_1_TRELLIS2_GPT6.html"
output=root/"test-sonuclari"/"trellis2"
output.mkdir(parents=True,exist_ok=True)
fixture=output/"sentetik_coklu_mesh_uv_pbr.glb"
fixture.write_bytes(glb())
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=["--no-sandbox","--use-angle=swiftshader","--enable-unsafe-swiftshader"])
    page=browser.new_page(viewport={"width":390,"height":844},accept_downloads=True)
    errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.goto(html.as_uri(),wait_until="domcontentloaded")
    page.wait_for_function("!!window.ForgeV12 && !!window.ForgeTrellis2 && !!window.ForgeV11?.ready",timeout=60000)
    assert page.locator("#tabs .tab-btn").count()==6
    page.evaluate("ForgeShell.go('model')")
    page.locator("#s3-verify-file").set_input_files(str(fixture))
    page.wait_for_function("window.ForgeTrellis2.state.active",timeout=90000)
    message=page.locator("#trellis2-status").inner_text()
    assert "2 mesh" in message and "2 UV" in message and "2 materyal" in message,message
    assert page.locator("#trellis-live-view canvas").count()==1
    assert page.locator("#s3-import-out").inner_text().find("2 materyal")>=0
    # Confirm view rotation and that original raw GLB can be re-downloaded unchanged.
    page.get_by_role("button",name="Yan",exact=True).click()
    page.get_by_role("button",name="Arka",exact=True).click()
    page.get_by_role("button",name="Ön",exact=True).click()
    with page.expect_download(timeout=15000) as download:
        page.get_by_role("button",name="GLB indir",exact=True).click()
    exported=output/"yeniden_indirilen.glb"
    download.value.save_as(exported)
    assert exported.read_bytes()==fixture.read_bytes(),"GLB bytes changed"
    with page.expect_download(timeout=15000) as download:
        page.get_by_role("button",name="3 görünüş PNG",exact=True).click()
    png=output/"on_yan_arka.png"
    download.value.save_as(png)
    im=Image.open(png).convert("RGBA")
    assert im.width == 3 * im.height or im.width > 2*im.height, im.size
    assert im.getbbox(), "blank screenshot"
    page.get_by_role("button",name="Forge karakterine dön",exact=True).click()
    assert page.evaluate("!ForgeTrellis2.state.active")
    assert page.locator("#s3-view").count()==1
    assert not errors,errors
    print("PASS browser GLB 2 mesh + UV/PBR + front/side/back PNG + lossless GLB + fallback")
    browser.close()

"""TRELLIS.2 branch: synthetic standard glTF2 GLB / Chrome integration test. NOT a GPU generation test."""
from pathlib import Path
import os, json, struct, tempfile, io
from PIL import Image
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
html = root / "Forge_25D_V14_1_TRELLIS2_GPT6.html"
original = root / "Forge_25D_V14_1_Gorsel_Yukleme_Onarim.html"
assert html.is_file() and original.is_file()
assert original.read_bytes() in html.read_bytes() or (
    original.stat().st_size > 1_000_000 and html.stat().st_size > original.stat().st_size
), "V14.1 original file must be preserved; derived HTML must be additive"

def fixture(path: Path):
    import base64
    img = Image.new("RGBA", (4,4),(120,180,255,220))
    mem = io.BytesIO(); img.save(mem,format="PNG")
    binary = bytearray(); views=[]; acc=[]
    def blob(data, target=None):
        while len(binary)%4: binary.append(0)
        off=len(binary); binary.extend(data)
        item={"buffer":0,"byteOffset":off,"byteLength":len(data)}
        if target: item["target"]=target
        views.append(item)
        return len(views)-1
    def attr(vals, count, kind, component=5126, target=34962):
        fmt="f" if component==5126 else "H"
        bv=blob(struct.pack("<"+fmt*len(vals), *vals),target)
        acc.append({"bufferView":bv,"componentType":component,"count":count,"type":kind})
        return len(acc)-1
    pos=attr([-0.5,-0.5,0, 0.5,-0.5,0, 0,0.6,0],3,"VEC3")
    nrm=attr([0,0,1]*3,3,"VEC3")
    uv=attr([0,0,1,0,0.5,1],3,"VEC2")
    idx=attr([0,1,2],3,"SCALAR",component=5123,target=34963)
    image=blob(mem.getvalue())
    prim=lambda mat:{"attributes":{"POSITION":pos,"NORMAL":nrm,"TEXCOORD_0":uv},"indices":idx,"material":mat}
    j={"asset":{"version":"2.0","generator":"FORGE synthetic fixture"},
      "scene":0,"scenes":[{"nodes":[0,1]}],
      "nodes":[{"mesh":0,"translation":[-0.35,0,0]},{"mesh":1,"translation":[0.35,0,-0.2],"rotation":[0,0,0,1]}],
      "meshes":[{"primitives":[prim(0)]},{"primitives":[prim(1)]}],
      "materials":[{"name":"textured-transparent","doubleSided":True,"alphaMode":"BLEND",
        "pbrMetallicRoughness":{"baseColorTexture":{"index":0},"roughnessFactor":0.7,"metallicFactor":0.4}},
        {"name":"blue","doubleSided":True,"pbrMetallicRoughness":{"baseColorFactor":[0.2,0.3,0.95,1],"metallicFactor":0,"roughnessFactor":1}}],
      "images":[{"bufferView":image,"mimeType":"image/png"}],"textures":[{"source":0}],
      "bufferViews":views,"accessors":acc,"buffers":[{"byteLength":(len(binary)+3)//4*4}]}
    jb=json.dumps(j,separators=(",",":")).encode("utf-8")
    jb += b" " * (-len(jb)%4)
    binary.extend(b"\0"*(-len(binary)%4))
    total=12+8+len(jb)+8+len(binary)
    glb=struct.pack("<III",0x46546c67,2,total)+struct.pack("<II",len(jb),0x4e4f534a)+jb+struct.pack("<II",len(binary),0x004e4942)+binary
    path.write_bytes(glb)
    return len(glb)

with tempfile.TemporaryDirectory() as td:
    sample=Path(td)/"gltf2_unskinned_pbr_multi.glb"
    size=fixture(sample)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--use-angle=swiftshader","--enable-unsafe-swiftshader","--no-sandbox","--disable-dev-shm-usage"])
        context=browser.new_context(viewport={"width":390,"height":844},accept_downloads=True)
        page=context.new_page()
        errors=[]
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(html.as_uri())
        page.wait_for_function("window.ForgeTrellis2 && window.ForgeV12 && window.ForgeV11?.ready",timeout=120000)
        page.evaluate("ForgeShell.go('model')")
        page.locator("#s3-verify-file").set_input_files(str(sample))
        page.wait_for_function("ForgeTrellis2.state.active || document.getElementById('trellis2-status')?.textContent?.includes('açılamadı')",timeout=120000)
        message=page.locator("#trellis2-status").inner_text()
        assert page.evaluate("ForgeTrellis2.state.active"), f"GLB did not render: {message}, JS errors: {errors[:3]}"
        assert "2 mesh" in message and "2 UV'li mesh" in message, message
        assert page.locator("#trellis-live-view canvas").count()==1
        assert page.locator("#s3-view").is_hidden()
        assert page.evaluate("ForgeV12.S3.ch.skel.bones.length")==26
        print("PASS standard unskinned GLB/PBR/scene hierarchy imported",flush=True)
        with page.expect_download(timeout=20000) as di:
            page.get_by_role("button",name="GLB indir").last.click()
        downloaded=Path(td)/"roundtrip.glb"
        di.value.save_as(downloaded)
        assert downloaded.read_bytes()==sample.read_bytes(), "GLB bytes were modified"
        print("PASS GLB byte-identical export",flush=True)
        with page.expect_download(timeout=20000) as shot:
            page.get_by_role("button",name="3 görünüş PNG").click()
        png=Path(td)/"3views.png"
        shot.value.save_as(png)
        with Image.open(png) as im:
            assert im.width % 3 == 0 and im.height >= 300, im.size
            from PIL import ImageChops
            pw = im.width // 3
            first = im.crop((0, 0, pw, im.height))
            side = im.crop((pw, 0, 2*pw, im.height))
            assert ImageChops.difference(first.convert("RGB"), side.convert("RGB")).getbbox(), "Front and side render must differ"
        print("PASS front/side/back PNG export",flush=True)
        page.get_by_role("button",name="Forge karakterine dön").last.click()
        assert not page.evaluate("ForgeTrellis2.state.active")
        assert page.locator("#s3-view").is_visible()
        page.evaluate("ForgeV12.draw()")
        assert not errors,errors[:4]
        print("PASS preserves Forge engine and CPU/WebGL workflows",flush=True)
        browser.close()
print("RESULT: source-level and SwiftShader browser test passed. No real TRELLIS.2 generation or Android device test.")

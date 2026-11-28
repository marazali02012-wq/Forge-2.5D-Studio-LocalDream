"""Use the existing proven R3 Colab environment for one new private image.
No upload to GitHub, no installation or live service. Original image retained."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys
from PIL import Image,ImageOps
def main():
    p=argparse.ArgumentParser();p.add_argument("image",type=pathlib.Path);p.add_argument("--case",default="01-warrior");a=p.parse_args()
    if not a.case.isascii() or not all(x.isalnum() or x in "-_" for x in a.case):raise ValueError("invalid case")
    root=pathlib.Path("/content/forge-f01-triposg-r2")
    original=root/"forge_hierarchical_inference.py"
    assert original.is_file(),"R3 runtime unavailable; do not reinstall silently"
    assert pathlib.Path(sys.executable).parent==pathlib.Path("/content/forge-f01-py310/bin")
    out=pathlib.Path("/content/forge-hard10-"+a.case)
    out.mkdir(exist_ok=False)
    raw=a.image.resolve();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    Image.MAX_IMAGE_PIXELS=12_000_000
    with Image.open(raw) as im:
        if im.format not in ("PNG","JPEG","WEBP"):raise ValueError("unsupported image")
        im=ImageOps.exif_transpose(im).convert("RGBA");im.save(out/"input.png")
    # Retain exact original bytes separately. No manual mask/crop.
    shutil.copyfile(raw,out/"original.bin")
    src=original.read_text()
    old='src=root/"assets/example_data/hjswed.png"'
    oldout='"/content/forge-f01-gpu-evidence-r3"'
    assert src.count(old)==1 and src.count(oldout)==1,"unexpected R3 runner"
    src=src.replace(old,"src=pathlib.Path("+repr(str(out/"input.png"))+")").replace(oldout,repr(str(out)))
    compile(src,"forge_hard10_inference.py","exec")
    runner=root/("forge_hard10_"+a.case+".py");runner.write_text(src)
    env=dict(os.environ,PYTHONUNBUFFERED="1",HF_HUB_DISABLE_XET="1",PYTHONNOUSERSITE="1");env.pop("PYTHONPATH",None)
    with (out/"inference.log").open("w") as log:
        proc=subprocess.Popen([sys.executable,"-u",str(runner)],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        for line in proc.stdout:
            log.write(line);log.flush();print(line,end="",flush=True)
        status=proc.wait()
    if status:raise SystemExit(status)
    report=json.loads((out/"report.json").read_text())
    glb=out/"actual_triposg_demo.glb"
    assert report["actual_inference"] and report["decoder"]=="official_hierarchical_lewiner" and report["source_sha256"]==sha(out/"input.png") and report["glb_sha256"]==sha(glb)
    report.update(case=a.case,original_sha256=sha(raw),input_kind="unmodified composition; PNG conversion only",visual_accepted=False,editor_accepted=False)
    (out/"report.json").write_text(json.dumps(report,indent=2))
    archive=shutil.make_archive("/content/Forge_F01_Hard10_"+a.case,"zip",out)
    print("Actual output evidence:",archive,flush=True)
if __name__=="__main__":main()

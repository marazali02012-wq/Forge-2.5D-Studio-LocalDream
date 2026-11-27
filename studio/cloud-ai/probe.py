import json, pathlib, tempfile, struct, shutil
from gradio_client import Client, handle_file
from PIL import Image, ImageDraw
out=pathlib.Path("cloud-qa");out.mkdir(exist_ok=True)
report={"provider":"stabilityai/TripoSR","anonymous":True,"real_generation":False}
try:
    # New synthetic test image, no player data or credentials, not a cached demo.
    im=Image.new("RGB",(384,384),(210,210,210))
    d=ImageDraw.Draw(im)
    d.polygon([(88,150),(204,85),(310,146),(196,211)],fill=(100,175,220))
    d.polygon([(88,150),(196,211),(196,322),(88,262)],fill=(42,99,166))
    d.polygon([(196,211),(310,146),(310,258),(196,322)],fill=(32,63,118))
    f=out/"test-input.png";im.save(f)
    c=Client("stabilityai/TripoSR",verbose=False,download_files=str(out))
    api=c.view_api(return_format="dict")
    report["endpoints"]=list(api.get("named_endpoints",{}))
    assert "/preprocess" in report["endpoints"] and "/generate" in report["endpoints"],"Missing expected provider endpoints"
    processed=c.predict(handle_file(str(f)),False,0.85,api_name="/preprocess")
    result=c.predict(handle_file(processed),128,api_name="/generate")
    report["result_types"]=[type(v).__name__ for v in result]
    glb=pathlib.Path(result[1])
    data=glb.read_bytes()
    magic,version,length=struct.unpack_from("<4sII",data)
    assert magic==b"glTF" and version==2 and length==len(data)
    jslen,jstype=struct.unpack_from("<II",data,12)
    assert jstype==0x4e4f534a
    doc=json.loads(data[20:20+jslen])
    count=sum(doc["accessors"][pr["attributes"]["POSITION"]]["count"] for m in doc["meshes"] for pr in m["primitives"])
    assert count>0
    shutil.copyfile(glb,out/"generated.glb")
    report.update(real_generation=True,bytes=len(data),vertices=count)
except Exception as e:
    report["error"]=str(e)[:1500]
finally:
    (out/"report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if not report["real_generation"]:raise SystemExit(1)

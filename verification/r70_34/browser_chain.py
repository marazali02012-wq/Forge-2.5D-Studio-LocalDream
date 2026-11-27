from playwright.sync_api import sync_playwright
from pathlib import Path
import hashlib,json,os,time
out=Path(os.environ.get('FORGE_QA_OUTPUT','evidence34'))
out.mkdir(parents=True,exist_ok=True)
key=os.environ['FORGE_API_TOKEN']
api=os.environ.get('FORGE_QA_API','http://127.0.0.1:8785')
editor=os.environ.get('FORGE_QA_EDITOR','http://127.0.0.1:8788/Forge_R70_34_Studio.html')
inputs=Path(os.environ.get('FORGE_QA_IMAGES','cases'))
assert len(list(inputs.glob('*.png')))==10,'Provide all ten original character PNGs'
report={}
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path=os.environ.get('FORGE_QA_CHROMIUM'),args=['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader'])
 for i,src in enumerate(sorted(inputs.glob('*.png'))):
  w,h=[(800,360),(740,360),(667,375)][i%3]
  page=browser.new_page(viewport={'width':w,'height':h},has_touch=True,is_mobile=True)
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('dialog',lambda d:d.accept((api if 'adres' in d.message else key) if d.type=='prompt' else None))
  row={}
  try:
   page.goto(editor)
   page.click('#quickAi')
   with page.expect_file_chooser() as fc:page.locator('[data-forge-action=forgeRigGenerate]').click()
   start=time.monotonic()
   with page.expect_response(lambda r:r.url.endswith('/generate-rig') and r.request.method=='POST',timeout=430000) as req:fc.value.set_files(src)
   r=req.value;row.update(status=r.status,seconds=round(time.monotonic()-start,2),input_sha256=hashlib.sha256(src.read_bytes()).hexdigest())
   if r.status!=200:
    row['error']=page.locator('#msg').inner_text();raise RuntimeError('HTTP '+str(r.status))
   page.wait_for_function("document.querySelector('#rigClip').length===5",timeout=20000)
   view=page.locator('#animatedModel')
   for clip in ['idle','walk','attack','hurt','death']:
    page.select_option('#rigClip',clip)
    page.wait_for_function("(name)=>{let v=document.getElementById('animatedModel');return v.animationName===name&&v.currentTime>0.03}",arg=clip,timeout=6000)
    view.evaluate('e=>{e.pause();e.currentTime=e.duration/2}')
    page.screenshot(path=str(out/f'{src.stem}_clip_{clip}.jpg'),type='jpeg',quality=80)
   view.evaluate('e=>{e.pause();e.currentTime=0}')
   for angle in [0,90,180,270,45]:
    view.evaluate("(e,a)=>{e.cameraOrbit=a+'deg 85deg auto';e.jumpCameraToGoal()}",angle)
    page.wait_for_timeout(140)
    page.screenshot(path=str(out/f'{src.stem}_{angle}.jpg'),type='jpeg',quality=82)
   with page.expect_download() as dl:page.click('#saveRig')
   data=dl.value.path().read_bytes()
   assert len(data)==int(r.headers['content-length']) and data[:4]==b'glTF'
   (out/f'{src.stem}.glb').write_bytes(data)
   row.update(animations=5,angles=5,bytes=len(data),viewport=[w,h],overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth'))
  except Exception as e:row['failure']=str(e)
  row['page_errors']=errors
  report[src.stem]=row;(out/'e2e.json').write_text(json.dumps(report,indent=2));print(src.stem,row,flush=True);page.close()
 browser.close()

if any(row.get('status')!=200 or row.get('failure') or row.get('page_errors') or row.get('overflow') for row in report.values()):raise SystemExit(1)

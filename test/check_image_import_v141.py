"""Forge V14.1 image upload regression. Runs inside GitHub Actions Chrome."""
from pathlib import Path
import os
from PIL import Image
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parent.parent
html=root/'Forge_25D_V14_1_Gorsel_Yukleme_Onarim.html'
assets=root/'test'
assert html.is_file()
assert (assets/'izci.png').is_file()
src=Image.open(assets/'izci.png').convert('RGB')
for ext,fmt in [('jpg','JPEG'),('webp','WEBP')]: src.save(assets/f'import-test.{ext}',format=fmt)
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path=os.environ.get('CHROME_BIN','/usr/bin/google-chrome'),headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--no-sandbox','--disable-dev-shm-usage'])
 context=browser.new_context(offline=True,viewport={'width':390,'height':844})
 page=context.new_page()
 errors=[]
 page.on('pageerror',lambda err:errors.append(str(err)))
 page.goto(html.as_uri())
 page.wait_for_function('!!window.ForgeV12 && window.ForgeV11?.ready',timeout=120000)
 assert page.locator('#quickImageFile').count()==1
 assert page.locator('#importFile').count()==1
 assert page.locator('#ld-file').count()==1
 assert '.forgepack' in page.locator('#ld-file').get_attribute('accept')
 assert 'image/' in page.locator('#quickImageFile').get_attribute('accept')
 page.locator('#quickImageFile').set_input_files(str(assets/'izci.png'))
 page.wait_for_function("ForgeV11.state.customFileName==='izci.png'",timeout=15000)
 assert page.locator('#quickImageFile').input_value()==''
 assert 'Resim yüklendi:' in page.locator('#upload-status').inner_text()
 assert 'izci.png' in page.locator('#ed-src').inner_text()
 assert page.locator('#tab-duzenle').is_visible()
 print('PASS PNG first screen',flush=True)
 for ext in ('jpg','webp'):
  filename=f'import-test.{ext}'
  page.locator('#importFile').set_input_files(str(assets/filename))
  page.wait_for_function("name=>ForgeV11.state.customFileName===name",filename,timeout=15000)
  assert page.locator('#importFile').input_value()==''
  assert 'Resim yüklendi:' in page.locator('#ed-status').inner_text()
  print('PASS '+ext+' editor',flush=True)
 png=(assets/'izci.png').read_bytes()
 page.locator('#quickImageFile').set_input_files({'name':'android-image','mimeType':'application/octet-stream','buffer':png})
 page.wait_for_function("ForgeV11.state.customFileName==='android-image'",timeout=15000)
 assert 'Resim yüklendi:' in page.locator('#upload-status').inner_text()
 print('PASS Android generic MIME',flush=True)
 page.locator('#quickImageFile').set_input_files({'name':'fake.png','mimeType':'image/png','buffer':b'not a png'})
 page.wait_for_function("document.getElementById('upload-status').textContent.includes('Resim yüklenemedi')",timeout=15000)
 assert page.evaluate("ForgeV11.state.customFileName==='android-image'")
 print('PASS invalid image error',flush=True)
 page.locator('#quickImageFile').set_input_files(str(assets/'izci.png'))
 page.wait_for_function("ForgeV11.state.customFileName==='izci.png'",timeout=15000)
 page.evaluate("ForgeShell.go('model');document.getElementById('s3-analyze').click()")
 page.wait_for_function('ForgeV12.S3.ch?.mesh?.texture && ForgeV12.S3.atlas',timeout=120000)
 assert page.evaluate("ForgeV12.S3.ch.mesh.texture.rgba.length>10000")
 assert not errors,errors[:5]
 print('PASS image -> real 3D UV atlas',flush=True)
 browser.close()
for ext in ('jpg','webp'): (assets/f'import-test.{ext}').unlink(missing_ok=True)

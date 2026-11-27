// Dedicated view preserves the skin, texture and animation bytes during export.
let rigUrl;
const rigDialog = document.getElementById('rigDialog');
const rigView = document.getElementById('animatedModel');
const rigClip = document.getElementById('rigClip');
function openAnimated(blob) {
  if (rigUrl) URL.revokeObjectURL(rigUrl);
  rigUrl = URL.createObjectURL(blob);
  rigClip.replaceChildren();
  rigView.src = rigUrl;
  document.getElementById('saveRig').href = rigUrl;
  rigDialog.showModal();
}
rigView.addEventListener('load', () => {
  for (const name of rigView.availableAnimations) rigClip.add(new Option(name,name));
  if (rigClip.length) { rigView.animationName = rigClip.value; rigView.play(); }
});
rigView.addEventListener('error', () => { document.getElementById('rigStatus').textContent='GLB görüntülenemedi'; });
rigClip.onchange = () => { rigView.animationName=rigClip.value; rigView.play(); };
document.getElementById('closeRig').onclick = () => rigDialog.close();
rigDialog.onclose = () => {
  rigView.pause(); rigView.removeAttribute('src'); URL.revokeObjectURL(rigUrl); rigUrl=null;
  document.getElementById('rigStatus').textContent='';
};
document.getElementById('openRig').onclick = () => document.getElementById('rigFile').click();
document.getElementById('rigFile').onchange = e => {
  const file=e.target.files[0]; e.target.value='';
  if (file && file.size<=32*1024*1024) openAnimated(file);
  else if(file) alert('Animasyonlu GLB en fazla 32 MB');
};
const aiTools=document.getElementById('aiTools');
document.getElementById('quickAi').onclick=()=>aiTools.showModal();
document.getElementById('closeAiTools').onclick=()=>aiTools.close();
aiTools.querySelectorAll('[data-forge-action]').forEach(button=>{
  button.onclick=()=>{aiTools.close();document.getElementById(button.dataset.forgeAction).click()};
});

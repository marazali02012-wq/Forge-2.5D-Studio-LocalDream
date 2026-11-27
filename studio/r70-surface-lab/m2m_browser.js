import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {MeshoptDecoder} from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import {Rig} from './deps/mesh2motion/src/retarget/human-retargeting/Rig.ts';
import {HumanClipRetargeter} from './deps/mesh2motion/src/retarget/human-retargeting/HumanClipRetargeter.ts';
const loader=new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
const parse=b=>loader.parseAsync(Uint8Array.from(atob(b),c=>c.charCodeAt(0)).buffer,'');
const check=(x,m)=>{if(!x)throw Error(m)};
const srcConfig={pelvis:['pelvis'],spine:['spine_01','spine_03'],head:['neck_01','head'],armL:['clavicle_l','upperarm_l','lowerarm_l','hand_l'],armR:['clavicle_r','upperarm_r','lowerarm_r','hand_r'],legL:['thigh_l','calf_l','foot_l','ball_l'],legR:['thigh_r','calf_r','foot_r','ball_r']};
const targetNames={pelvis:['hips'],spine:['spine','chest'],head:['neck','head'],armL:['shoulder.L','upperarm.L','forearm.L','hand.L'],armR:['shoulder.R','upperarm.R','forearm.R','hand.R'],legL:['thigh.L','shin.L','foot.L','toe.L'],legR:['thigh.R','shin.R','foot.R','toe.R']};
function collect(g){
 const all=[];g.scene.traverse(o=>{if(o.isBone)all.push(o)});
 const meshes=[];g.scene.traverse(o=>{if(o.isSkinnedMesh)meshes.push(o)});
 const sk=meshes[0]?.skeleton||new THREE.Skeleton(all);
 check(sk.bones.length>0,'No bones in rig');
 const original=new Map();for(const b of sk.bones){
  const assoc=g.parser.associations.get(b);const name=g.parser.json.nodes[assoc?.nodes]?.name||b.name;
  original.set(name,b.name);
 }
 return {sk,meshes,original};
}
function config(c,original){return Object.fromEntries(Object.entries(c).map(([key,arr])=>[key,arr.map(n=>{check(original.has(n),'Missing bone '+n);return original.get(n)})]))}
function snapshot(sk){return sk.bones.map(b=>({p:b.position.clone(),q:b.quaternion.clone(),s:b.scale.clone()}))}
function restore(sk,rest){sk.bones.forEach((b,i)=>{b.position.copy(rest[i].p);b.quaternion.copy(rest[i].q);b.scale.copy(rest[i].s)});sk.bones[0].parent?.updateMatrixWorld(true)}
// Match segment directions in each rig's actual rest pose (A vs T pose).
// Set the corresponding perpendicular twist axis in the joint's local frame.
function calibratedRig(sk,c,meshes){
 const rig=new Rig(sk).fromConfig(c);
 for(const key of ['armL','armR','legL','legR']){
  const chain=rig.chains[key];
  for(let i=0;i<chain.length-(key.startsWith('arm')?0:1);i++){
   const item=chain[i],bone=sk.bones[item.idx],child=chain[i+1]&&sk.bones[chain[i+1].idx];
   const p=bone.getWorldPosition(new THREE.Vector3());
   let v;
   if(child) v=child.getWorldPosition(new THREE.Vector3()).sub(p);
   else {
    // Palm direction from actual source finger roots when available.
    const fingers=bone.children.filter(b=>b.isBone&&/index|middle|ring|pinky/i.test(b.name));
    if(fingers.length){
     v=new THREE.Vector3();for(const f of fingers)v.add(f.getWorldPosition(new THREE.Vector3()).sub(p));v.multiplyScalar(1/fingers.length);
    }else{
     // Forge has a single hand bone, so estimate palm axis from its actual weighted geometry.
     const prev=sk.bones[chain[i-1].idx].getWorldPosition(new THREE.Vector3()),axis=p.clone().sub(prev).normalize();
     const mean=new THREE.Vector3(),pt=new THREE.Vector3();let n=0;
     for(const m of meshes){if(!m.name.includes('human')||!m.geometry.attributes.skinIndex)continue;
      const ix=m.geometry.attributes.skinIndex,wt=m.geometry.attributes.skinWeight,ps=m.geometry.attributes.position;
      for(let k=0;k<ps.count;k++){
       let w=0;for(let j=0;j<4;j++)if(ix.array[k*4+j]===item.idx)w+=wt.array[k*4+j];
       if(w<.75)continue;
       pt.fromBufferAttribute(ps,k).applyMatrix4(m.matrixWorld).sub(p);
       if(pt.dot(axis)<=.02)continue;
       mean.add(pt);n++;
      }
     }
     v=n?mean.multiplyScalar(1/n):axis;
    }
   }
   check(v.length()>1e-5,'Zero-length limb segment '+bone.name);v.normalize();
   const twist=key.startsWith('arm')?new THREE.Vector3(0,0,-1):new THREE.Vector3(1,0,0);
   twist.addScaledVector(v,-twist.dot(v)).normalize();
   check(twist.length()>.9,'Invalid perpendicular axis '+bone.name);
   const inv=bone.getWorldQuaternion(new THREE.Quaternion()).invert();
   v.applyQuaternion(inv);twist.applyQuaternion(inv);
   item.swing[0]=v.x;item.swing[1]=v.y;item.swing[2]=v.z;
   item.twist[0]=twist.x;item.twist[1]=twist.y;item.twist[2]=twist.z;
  }
 }
 return rig;
}
// Ground the baked contact poses using actual skinned vertices, not the bone tips.
// No change to X/Z travel. Reject excessive correction rather than hiding a bad pose.
function groundClip(baked,t,rest,restFloor,height){
 restore(t.sk,rest);
 const posTrack=baked.tracks.find(x=>x.name.endsWith('.position'));check(posTrack,'Missing pelvis track');
 const byName=new Map(t.sk.bones.map(b=>[b.name,b]));
 const quatTracks=baked.tracks.filter(x=>x.name.endsWith('.quaternion'));
 const bone=byName.get(posTrack.name.slice(0,-9));check(bone,'Unknown pelvis track');
 const p=new THREE.Vector3();let max=0;
 const worldToParent=new THREE.Matrix3().setFromMatrix4(bone.parent.matrixWorld).invert();
 for(let f=0;f<posTrack.times.length;f++){
  for(const track of quatTracks){const b=byName.get(track.name.slice(0,-11));check(b,'Unknown rotation track');b.quaternion.fromArray(track.values,f*4)}
  bone.position.fromArray(posTrack.values,f*3);t.sk.bones[0].parent?.updateMatrixWorld(true);
  let min=Infinity;
  for(const m of t.meshes){const a=m.geometry.attributes.position;for(let i=0;i<a.count;i++){
   p.fromBufferAttribute(a,i);m.applyBoneTransform(i,p);p.applyMatrix4(m.matrixWorld);min=Math.min(min,p.y);
  }}
  const shift=restFloor-min;check(Number.isFinite(shift)&&Math.abs(shift)<height*.08,'Ground correction excessive '+baked.name);
  const local=new THREE.Vector3(0,shift,0).applyMatrix3(worldToParent);
  posTrack.values[f*3]+=local.x;posTrack.values[f*3+1]+=local.y;posTrack.values[f*3+2]+=local.z;
  max=Math.max(max,Math.abs(shift)/height);
 }
 restore(t.sk,rest);return max;
}
window.forgeRetarget=async (input)=>{
 const target=await parse(input.target),source=await parse(input.source);
 const t=collect(target),s=collect(source);
 check(t.sk.bones.length===26,'Forge skeleton count');
 check(t.meshes.length===10,'Forge mesh count');
 const tc=config(targetNames,t.original),sc=config(srcConfig,s.original);
 const tr=snapshot(t.sk),sr=snapshot(s.sk);
 const rev=new Map([...t.original].map(([a,b])=>[b,a]));
 const output=[];
 target.scene.updateMatrixWorld(true);const restBox=new THREE.Box3().setFromObject(target.scene,true),height=restBox.max.y-restBox.min.y;
 for(const [name,bytes] of Object.entries(input.clips)){
  restore(t.sk,tr);restore(s.sk,sr);
  const gltf=await parse(bytes);
  check(gltf.animations.length===1,'Expected one library clip '+name);
  const c=gltf.animations[0];
  const baked=HumanClipRetargeter.retarget(c,calibratedRig(s.sk,sc,s.meshes),calibratedRig(t.sk,tc,t.meshes),{clip_name:'m2m_'+name,fps:30});
  check(baked.tracks.length>=20,'Insufficient baked tracks');
  const maxGroundCorrection=groundClip(baked,t,tr,restBox.min.y,height);
  const tracks=baked.tracks.map(track=>{
   const split=track.name.lastIndexOf('.'),name=rev.get(track.name.slice(0,split)),type=track.name.slice(split+1);
   check(name&&['quaternion','position'].includes(type),'Unknown target track '+track.name);
   check(track.values.every(Number.isFinite)&&track.times.every(Number.isFinite),'Nonfinite tracks');
   check(track.times.every((v,i)=>!i||v>track.times[i-1]),'Invalid track times');
   return {name,type,times:Array.from(track.times),values:Array.from(track.values)};
  });
  output.push({name:baked.name,duration:baked.duration,tracks,maxGroundCorrection});
 }
 return {sourceBones:s.sk.bones.map(b=>b.name),targetBones:[...t.original.keys()],clips:output};
};
let renderer,scene,camera,model,mixer,rest,meshes,ground;
window.forgeLoadPreview=async b=>{
 const gltf=await parse(b);model=gltf.scene;meshes=collect(gltf).meshes;
 model.updateMatrixWorld(true);
 scene=new THREE.Scene();scene.background=new THREE.Color(0x17212c);scene.add(model);
 const box=new THREE.Box3().setFromObject(model,true),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());
 const h=size.y;check(h>0&&h<100,'Invalid height');
 camera=new THREE.PerspectiveCamera(34,800/450,.01,h*30);
 camera.position.set(center.x,center.y+h*.12,center.z+h*1.95);camera.lookAt(center);
 scene.add(new THREE.HemisphereLight(0xffffff,0x718094,2.2));
 const l=new THREE.DirectionalLight(0xffffff,3.0);l.position.set(3,5,4);scene.add(l);
 const fill=new THREE.DirectionalLight(0xb8d5ff,1.1);fill.position.set(-3,2,-4);scene.add(fill);
 ground=new THREE.GridHelper(h*3,20,0x63778a,0x324355);ground.position.y=box.min.y;scene.add(ground);
 renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});renderer.setSize(800,450);document.body.appendChild(renderer.domElement);
 mixer=new THREE.AnimationMixer(model);rest={center,h,box,sk:collect(gltf).sk};rest.transforms=snapshot(rest.sk);
 window.forgePreviewClips=gltf.animations;
 return {animations:gltf.animations.map(a=>({name:a.name,duration:a.duration})),height:h,restGround:box.min.y};
};
window.forgeFrame=(name,fraction,angle=0)=>{
 const clip=window.forgePreviewClips.find(c=>c.name===name);check(clip,'Clip missing '+name);
 mixer.stopAllAction();restore(rest.sk,rest.transforms);mixer.setTime(0);
 const action=mixer.clipAction(clip);action.reset().setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.play();mixer.setTime(clip.duration*fraction);
 model.updateMatrixWorld(true);
 let minY=Infinity,maxY=-Infinity,maxRadius=0,finite=true,n=0;
 const v=new THREE.Vector3();
 for(const m of meshes){const p=m.geometry.attributes.position;for(let i=0;i<p.count;i++){v.fromBufferAttribute(p,i);m.applyBoneTransform(i,v);v.applyMatrix4(m.matrixWorld);finite=finite&&Number.isFinite(v.x+v.y+v.z);minY=Math.min(minY,v.y);maxY=Math.max(maxY,v.y);maxRadius=Math.max(maxRadius,v.distanceTo(rest.center));n++}}
 const c=rest.center,h=rest.h;camera.position.set(c.x+Math.sin(angle)*h*1.95,c.y+h*.12,c.z+Math.cos(angle)*h*1.95);camera.lookAt(c);renderer.render(scene,camera);
 document.querySelector('#label').textContent=name+' '+Math.round(fraction*100)+'%';
 return {finite,vertices:n,minY,maxY,maxRadiusOverHeight:maxRadius/h,groundOffset:(minY-rest.box.min.y)/h};
};

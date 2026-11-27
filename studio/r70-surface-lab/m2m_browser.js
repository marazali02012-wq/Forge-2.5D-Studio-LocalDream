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
function calibratedRig(sk,c){
 const rig=new Rig(sk).fromConfig(c);
 for(const key of ['armL','armR','legL','legR']){
  const chain=rig.chains[key];
  for(let i=0;i<chain.length-1;i++){
   const item=chain[i],bone=sk.bones[item.idx],child=sk.bones[chain[i+1].idx];
   const p=bone.getWorldPosition(new THREE.Vector3()),v=child.getWorldPosition(new THREE.Vector3()).sub(p);
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
window.forgeRetarget=async (input)=>{
 const target=await parse(input.target),source=await parse(input.source);
 const t=collect(target),s=collect(source);
 check(t.sk.bones.length===26,'Forge skeleton count');
 check(t.meshes.length===10,'Forge mesh count');
 const tc=config(targetNames,t.original),sc=config(srcConfig,s.original);
 const tr=snapshot(t.sk),sr=snapshot(s.sk);
 const rev=new Map([...t.original].map(([a,b])=>[b,a]));
 const output=[];
 for(const [name,bytes] of Object.entries(input.clips)){
  restore(t.sk,tr);restore(s.sk,sr);
  const gltf=await parse(bytes);
  check(gltf.animations.length===1,'Expected one library clip '+name);
  const c=gltf.animations[0];
  const baked=HumanClipRetargeter.retarget(c,calibratedRig(s.sk,sc),calibratedRig(t.sk,tc),{clip_name:'m2m_'+name,fps:30});
  check(baked.tracks.length>=20,'Insufficient baked tracks');
  const tracks=baked.tracks.map(track=>{
   const split=track.name.lastIndexOf('.'),name=rev.get(track.name.slice(0,split)),type=track.name.slice(split+1);
   check(name&&['quaternion','position'].includes(type),'Unknown target track '+track.name);
   check(track.values.every(Number.isFinite)&&track.times.every(Number.isFinite),'Nonfinite tracks');
   check(track.times.every((v,i)=>!i||v>track.times[i-1]),'Invalid track times');
   return {name,type,times:Array.from(track.times),values:Array.from(track.values)};
  });
  output.push({name:baked.name,duration:baked.duration,tracks});
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

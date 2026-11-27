package com.forgestudio.mobileprobe;
import ai.onnxruntime.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.function.Consumer;

public final class Engine {
 public static final String ENCODER_SHA="8a94284bc2c914323e17774a247e47de0dd5b3a6843d026c68b2765c68a67cbd";
 public static final long ENCODER_BYTES=433359857L;
 public static final String DECODER_SHA="1604a0dc1903eee485d5a388dd2b4bcac8fad484a96010a797d7c1f40583d985";
 public static String sha(File f)throws Exception{
  MessageDigest d=MessageDigest.getInstance("SHA-256");
  try(InputStream in=new BufferedInputStream(new FileInputStream(f))){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)d.update(b,0,n);}
  StringBuilder s=new StringBuilder();for(byte b:d.digest())s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();
 }
 public static OrtSession.SessionOptions options()throws OrtException{
  OrtSession.SessionOptions o=new OrtSession.SessionOptions();
  o.setIntraOpNumThreads(1);o.setInterOpNumThreads(1);o.setCPUArenaAllocator(false);o.setMemoryPatternOptimization(false);
  o.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.NO_OPT);
  o.addConfigEntry("session.disable_prepacking","1");return o;
 }
 public static long hwm(){
  try(BufferedReader r=new BufferedReader(new FileReader("/proc/self/status"))){String s;while((s=r.readLine())!=null)if(s.startsWith("VmHWM:"))return Long.parseLong(s.trim().split("\\s+")[1])/1024;}catch(Exception ignored){}return -1;
 }
 static float[] floats(OnnxValue v){FloatBuffer b=((OnnxTensor)v).getFloatBuffer();float[] a=new float[b.remaining()];b.get(a);return a;}
 public static Mesh run(File encoder,File decoder,float[] input,float radius,float iso,int n,Consumer<String> log)throws Exception{
  if(input.length!=3*512*512||n<24||n>96||radius<=0||!Float.isFinite(iso))throw new IllegalArgumentException("Gecersiz girdi");
  if(encoder.length()!=ENCODER_BYTES||!sha(encoder).equals(ENCODER_SHA)||!sha(decoder).equals(DECODER_SHA))throw new IOException("Model SHA256 dogrulanamadi");
  long start=System.nanoTime();OrtEnvironment env=OrtEnvironment.getEnvironment();
  float[] plane;
  log.accept("Encoder yukleniyor...");
  try(OrtSession.SessionOptions o=options();OrtSession s=env.createSession(encoder.getAbsolutePath(),o);OnnxTensor x=OnnxTensor.createTensor(env,FloatBuffer.wrap(input),new long[]{1,3,512,512})){
   log.accept("Encoder hesapliyor | RAM tepe: "+hwm()+" MiB");
   try(OrtSession.Result out=s.run(Collections.singletonMap(s.getInputNames().iterator().next(),x))){plane=floats(out.get(0));}
  }
  if(plane.length!=3*40*64*64)throw new IOException("Triplane boyutu beklenenden farkli");
  log.accept("Encoder bitti | RAM tepe: "+hwm()+" MiB");
  int count=n*n*n;float[] density=new float[count];Mesh mesh;
  try(OrtSession.SessionOptions o=options();OrtSession s=env.createSession(decoder.getAbsolutePath(),o);OnnxTensor p=OnnxTensor.createTensor(env,FloatBuffer.wrap(plane),new long[]{1,3,40,64,64})){
   for(int offset=0;offset<count;offset+=4096){
    int len=Math.min(4096,count-offset);float[] points=new float[len*3];
    for(int i=0;i<len;i++){int a=offset+i;points[i*3]=coord(a/(n*n),n,radius);points[i*3+1]=coord((a/n)%n,n,radius);points[i*3+2]=coord(a%n,n,radius);}
    float[] d=decode(env,s,p,points,"density");if(d.length!=len)throw new IOException("Density boyutu");
    for(float z:d)if(!Float.isFinite(z))throw new IOException("Density NaN");
    System.arraycopy(d,0,density,offset,len);
    if(offset%(4096*8)==0)log.accept("3D alan: "+(100*offset/count)+"%");
   }
   mesh=extract(density,n,radius,iso);
   int beforeCleanup=mesh.f.size();
   mesh=clean(mesh,2*radius/(n-1));
   log.accept("Yuzey temizleme: "+beforeCleanup+" -> "+mesh.f.size()+" ucgen");
   if(mesh.f.size()<100||mesh.v.size()<30)throw new IOException("Yeterli 3D yuzey bulunamadi");
   for(int a=0;a<mesh.v.size();a+=4096){int len=Math.min(4096,mesh.v.size()-a);float[] points=new float[len*3];for(int i=0;i<len;i++)System.arraycopy(mesh.v.get(a+i),0,points,i*3,3);float[] c=decode(env,s,p,points,"color");if(c.length!=len*3)throw new IOException("Renk boyutu");for(int i=0;i<len;i++){float[] rgb=Arrays.copyOfRange(c,i*3,i*3+3);for(int j=0;j<3;j++){if(!Float.isFinite(rgb[j]))throw new IOException("Renk NaN");rgb[j]=Math.max(0,Math.min(1,rgb[j]));}mesh.c.add(rgb);}}
  }
  // cyclic coordinate rotation (x,y,z)->(y,z,x), determinant +1.
  for(float[] v:mesh.v){float x=v[0];v[0]=v[1];v[1]=v[2];v[2]=x;}
  mesh.elapsedMs=(System.nanoTime()-start)/1000000;mesh.hwmMiB=hwm();
  log.accept(mesh.v.size()+" kose / "+mesh.f.size()+" ucgen | "+mesh.elapsedMs/1000f+" sn | "+mesh.hwmMiB+" MiB");
  return mesh;
 }
 static float[] decode(OrtEnvironment env,OrtSession s,OnnxTensor planes,float[] xyz,String output)throws OrtException{
  try(OnnxTensor q=OnnxTensor.createTensor(env,FloatBuffer.wrap(xyz),new long[]{xyz.length/3,3})){
   Map<String,OnnxTensor> m=new HashMap<>();m.put("triplane",planes);m.put("points",q);
   try(OrtSession.Result r=s.run(m,Collections.singleton(output))){return floats(r.get(0));}
  }
 }
 static float coord(int i,int n,float r){return -r+2*r*i/(n-1);}
 static int id(int x,int y,int z,int n){return (x*n+y)*n+z;}
 static float[] xyz(int i,int n,float r){return new float[]{coord(i/(n*n),n,r),coord((i/n)%n,n,r),coord(i%n,n,r)};}
 public static final class Mesh{
  public final ArrayList<float[]> v=new ArrayList<>(),c=new ArrayList<>();
  public final ArrayList<int[]> f=new ArrayList<>();
  public long elapsedMs,hwmMiB;
 }
 // Remove only very small disconnected pieces; preserve substantial separate geometry.
 static int root(int[] p,int a){while(p[a]!=a){p[a]=p[p[a]];a=p[a];}return a;}
 static void union(int[] p,int a,int b){a=root(p,a);b=root(p,b);if(a!=b)p[b]=a;}
 static long edgeKey(int a,int b){return ((long)Math.min(a,b)<<32)|(Math.max(a,b)&0xffffffffL);}
 public static Mesh clean(Mesh source,float cell){
  int nv=source.v.size();int[] parent=new int[nv],counts=new int[nv],map=new int[nv];Arrays.fill(map,-1);
  for(int i=0;i<nv;i++)parent[i]=i;
  for(int[] f:source.f){union(parent,f[0],f[1]);union(parent,f[1],f[2]);}
  int largest=0;for(int[] f:source.f){int r=root(parent,f[0]);largest=Math.max(largest,++counts[r]);}
  int minimum=Math.max(8,(int)Math.ceil(largest*.002));Mesh m=new Mesh();
  for(int[] f:source.f){if(counts[root(parent,f[0])]<minimum)continue;
   int[] q=new int[3];for(int k=0;k<3;k++){int i=f[k];if(map[i]<0){map[i]=m.v.size();m.v.add(source.v.get(i).clone());if(source.c.size()==nv)m.c.add(source.c.get(i).clone());}q[k]=map[i];}m.f.add(q);
  }
  int n=m.v.size();if(n==0)return m;
  ArrayList<HashSet<Integer>> neighbors=new ArrayList<>(n);for(int i=0;i<n;i++)neighbors.add(new HashSet<>());
  HashMap<Long,Integer> edges=new HashMap<>();for(int[] f:m.f)for(int k=0;k<3;k++){int a=f[k],b=f[(k+1)%3];neighbors.get(a).add(b);neighbors.get(b).add(a);long key=edgeKey(a,b);edges.put(key,edges.getOrDefault(key,0)+1);}
  boolean[] fixed=new boolean[n];for(Map.Entry<Long,Integer> e:edges.entrySet())if(e.getValue()!=2){fixed[(int)(e.getKey()>>>32)]=true;fixed[(int)(long)e.getKey()]=true;}
  float[][] original=m.v.toArray(new float[0][]),cur=new float[n][3];for(int i=0;i<n;i++)cur[i]=original[i].clone();
  // Bounded Taubin smoothing: opposing passes limit shrinkage; freeze open/nonmanifold edges.
  for(float factor:new float[]{.42f,-.45f,.42f,-.45f,.42f,-.45f}){
   float[][] next=new float[n][3];
   for(int i=0;i<n;i++){float[] p=cur[i];next[i]=p.clone();if(fixed[i]||neighbors.get(i).isEmpty())continue;
    float[] avg=new float[3];for(int j:neighbors.get(i))for(int k=0;k<3;k++)avg[k]+=cur[j][k];
    for(int k=0;k<3;k++)next[i][k]+=factor*(avg[k]/neighbors.get(i).size()-p[k]);
    float[] d=sub(next[i],original[i]);float l=(float)Math.sqrt(dot(d,d)),limit=.45f*cell;if(l>limit)for(int k=0;k<3;k++)next[i][k]=original[i][k]+d[k]*limit/l;
   }cur=next;
  }
  // Reject smoothing if any face flips or collapses. Cleanup remains valid.
  boolean safe=true;for(int[] f:m.f){float[] a=cross(sub(original[f[1]],original[f[0]]),sub(original[f[2]],original[f[0]]));float[] b=cross(sub(cur[f[1]],cur[f[0]]),sub(cur[f[2]],cur[f[0]]));if(dot(a,b)<=0||dot(b,b)<1e-24f){safe=false;break;}}
  if(safe)for(int i=0;i<n;i++)m.v.set(i,cur[i]);
  return m;
 }
 public static float[][] normals(Mesh m){
  float[][] result=new float[m.v.size()][3];for(int[] f:m.f){float[] a=cross(sub(m.v.get(f[1]),m.v.get(f[0])),sub(m.v.get(f[2]),m.v.get(f[0])));for(int i:f)for(int j=0;j<3;j++)result[i][j]+=a[j];}
  for(float[] a:result){float l=(float)Math.sqrt(dot(a,a));for(int j=0;j<3;j++)a[j]=l>1e-12?a[j]/l:j==1?1:0;}return result;
 }
 static float[] sub(float[] a,float[] b){return new float[]{a[0]-b[0],a[1]-b[1],a[2]-b[2]};}
 static float[] cross(float[] a,float[] b){return new float[]{a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};}
 static float dot(float[] a,float[] b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
 static int vertex(int a,int b,float[] d,int n,float r,float iso,Mesh m,Map<Long,Integer> cache){
  int lo=Math.min(a,b),hi=Math.max(a,b);long key=((long)lo<<32)|(hi&0xffffffffL);Integer old=cache.get(key);if(old!=null)return old;
  float t=(iso-d[a])/(d[b]-d[a]);t=Math.max(.000001f,Math.min(.999999f,t));float[] p=xyz(a,n,r),q=xyz(b,n,r);
  for(int k=0;k<3;k++)p[k]+=(q[k]-p[k])*t;
  int i=m.v.size();m.v.add(p);cache.put(key,i);return i;
 }
 static void face(Mesh m,int a,int b,int c,float[] outward){
  if(a==b||b==c||a==c)return;float[] normal=cross(sub(m.v.get(b),m.v.get(a)),sub(m.v.get(c),m.v.get(a)));
  if(dot(normal,normal)<1e-24f)return;m.f.add(dot(normal,outward)>=0?new int[]{a,b,c}:new int[]{a,c,b});
 }
 public static Mesh extract(float[] d,int n,float r,float iso){
  Mesh m=new Mesh();Map<Long,Integer> cache=new HashMap<>();int[][] tets={{0,5,1,6},{0,1,2,6},{0,2,3,6},{0,3,7,6},{0,7,4,6},{0,4,5,6}};
  for(int x=0;x<n-1;x++)for(int y=0;y<n-1;y++)for(int z=0;z<n-1;z++){
   int[] q={id(x,y,z,n),id(x+1,y,z,n),id(x+1,y+1,z,n),id(x,y+1,z,n),id(x,y,z+1,n),id(x+1,y,z+1,n),id(x+1,y+1,z+1,n),id(x,y+1,z+1,n)};
   int inside=0;for(int i:q)if(d[i]>iso)inside++;if(inside==0||inside==8)continue;
   for(int[] tet:tets){int[] in=new int[4],out=new int[4];int ni=0,no=0;
    for(int j:tet){int a=q[j];if(d[a]>iso)in[ni++]=a;else out[no++]=a;}if(ni==0||no==0)continue;
    float[] direction=new float[3];for(int j=0;j<ni;j++){float[] p=xyz(in[j],n,r);for(int k=0;k<3;k++)direction[k]-=p[k]/ni;}for(int j=0;j<no;j++){float[] p=xyz(out[j],n,r);for(int k=0;k<3;k++)direction[k]+=p[k]/no;}
    if(ni==1)face(m,vertex(in[0],out[0],d,n,r,iso,m,cache),vertex(in[0],out[1],d,n,r,iso,m,cache),vertex(in[0],out[2],d,n,r,iso,m,cache),direction);
    else if(ni==3)face(m,vertex(out[0],in[0],d,n,r,iso,m,cache),vertex(out[0],in[1],d,n,r,iso,m,cache),vertex(out[0],in[2],d,n,r,iso,m,cache),direction);
    else{int a=vertex(in[0],out[0],d,n,r,iso,m,cache),b=vertex(in[0],out[1],d,n,r,iso,m,cache),c=vertex(in[1],out[0],d,n,r,iso,m,cache),e=vertex(in[1],out[1],d,n,r,iso,m,cache);face(m,a,b,e,direction);face(m,a,e,c,direction);}
   }
  }return m;
 }
 public static void saveGlb(Mesh m,File file)throws IOException{
  int nv=m.v.size(),nf=m.f.size(),len=nv*36+nf*12;ByteBuffer b=ByteBuffer.allocate(len).order(ByteOrder.LITTLE_ENDIAN);float[] min={Float.MAX_VALUE,Float.MAX_VALUE,Float.MAX_VALUE},max={-Float.MAX_VALUE,-Float.MAX_VALUE,-Float.MAX_VALUE};
  float[][] normal=normals(m);
  for(float[] p:m.v)for(int j=0;j<3;j++){min[j]=Math.min(min[j],p[j]);max[j]=Math.max(max[j],p[j]);b.putFloat(p[j]);}
  for(float[] a:normal){float l=(float)Math.sqrt(dot(a,a));for(int j=0;j<3;j++)b.putFloat(l>1e-12?a[j]/l:j==1?1:0);}
  for(float[] a:m.c)for(float x:a)b.putFloat(x);
  for(int[] f:m.f)for(int i:f)b.putInt(i);
  if(b.position()!=len)throw new IOException("GLB uzunluk");
  String json="{\"asset\":{\"version\":\"2.0\",\"generator\":\"Forge Android INT8\"},\"scene\":0,\"scenes\":[{\"nodes\":[0]}],\"nodes\":[{\"mesh\":0}],\"meshes\":[{\"primitives\":[{\"attributes\":{\"POSITION\":0,\"NORMAL\":1,\"COLOR_0\":2},\"indices\":3,\"material\":0}]}],\"materials\":[{\"pbrMetallicRoughness\":{\"metallicFactor\":0,\"roughnessFactor\":0.8}}],\"buffers\":[{\"byteLength\":"+len+"}],\"bufferViews\":[{\"buffer\":0,\"byteOffset\":0,\"byteLength\":"+(nv*12)+",\"target\":34962},{\"buffer\":0,\"byteOffset\":"+(nv*12)+",\"byteLength\":"+(nv*12)+",\"target\":34962},{\"buffer\":0,\"byteOffset\":"+(nv*24)+",\"byteLength\":"+(nv*12)+",\"target\":34962},{\"buffer\":0,\"byteOffset\":"+(nv*36)+",\"byteLength\":"+(nf*12)+",\"target\":34963}],\"accessors\":[{\"bufferView\":0,\"componentType\":5126,\"count\":"+nv+",\"type\":\"VEC3\",\"min\":"+Arrays.toString(min)+",\"max\":"+Arrays.toString(max)+"},{\"bufferView\":1,\"componentType\":5126,\"count\":"+nv+",\"type\":\"VEC3\"},{\"bufferView\":2,\"componentType\":5126,\"count\":"+nv+",\"type\":\"VEC3\"},{\"bufferView\":3,\"componentType\":5125,\"count\":"+(nf*3)+",\"type\":\"SCALAR\"}]}";
  byte[] j=json.getBytes(java.nio.charset.StandardCharsets.UTF_8);int pad=(4-j.length%4)%4;
  try(OutputStream out=new BufferedOutputStream(new FileOutputStream(file))){ByteBuffer header=ByteBuffer.allocate(20).order(ByteOrder.LITTLE_ENDIAN).putInt(0x46546c67).putInt(2).putInt(28+j.length+pad+len).putInt(j.length+pad).putInt(0x4e4f534a);out.write(header.array());out.write(j);for(int i=0;i<pad;i++)out.write(32);out.write(ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).putInt(len).putInt(0x004e4942).array());out.write(b.array());}
 }
}

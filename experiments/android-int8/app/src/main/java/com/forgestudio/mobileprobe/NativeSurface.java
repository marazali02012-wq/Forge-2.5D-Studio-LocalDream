package com.forgestudio.mobileprobe;
public final class NativeSurface{
 public static final boolean AVAILABLE;
 static{boolean ok=false;try{System.loadLibrary("forge_mc33");ok=true;}catch(UnsatisfiedLinkError ignored){}AVAILABLE=ok;}
 static native Object[] extract(float[] density,int n,float radius,float iso);
 public static Engine.Mesh run(float[] density,int n,float radius,float iso){
  if(!AVAILABLE)throw new IllegalStateException("MC33 native library missing");
  Object[] a=extract(density,n,radius,iso);float[] v=(float[])a[0];int[] f=(int[])a[1];
  if(v.length%3!=0||f.length%3!=0)throw new IllegalStateException("Invalid MC33 output");
  Engine.Mesh m=new Engine.Mesh();for(int i=0;i<v.length;i+=3)m.v.add(new float[]{v[i],v[i+1],v[i+2]});
  for(int i=0;i<f.length;i+=3){int x=f[i],y=f[i+1],z=f[i+2];if(x==y||x==z||y==z)throw new IllegalStateException("Duplicate face index");
   float[] norm=Engine.cross(Engine.sub(m.v.get(y),m.v.get(x)),Engine.sub(m.v.get(z),m.v.get(x)));if(Engine.dot(norm,norm)<1e-24f)throw new IllegalStateException("Degenerate MC33 face");m.f.add(new int[]{x,y,z});}
  return m;
 }
}

package com.forgestudio.mobileprobe;
import java.util.Arrays;
public final class Preview {
 public static final int SIZE=480;
 static int rgb(int r,int g,int b){return 0xff000000|(r<<16)|(g<<8)|b;}
 public static int[] pixels(Engine.Mesh m,int angle){
  final int size=480;int[] pixels=new int[size*size];Arrays.fill(pixels,rgb(24,29,36));float[] depth=new float[pixels.length];Arrays.fill(depth,Float.NEGATIVE_INFINITY);
  double yaw=angle*Math.PI/2,cs=Math.cos(yaw),sn=Math.sin(yaw);int nv=m.v.size();float[][] q=new float[nv][3],lit=new float[nv][3],normals=Engine.normals(m);float[] lo={Float.MAX_VALUE,Float.MAX_VALUE},hi={-Float.MAX_VALUE,-Float.MAX_VALUE};
  for(int i=0;i<nv;i++){float[] v=m.v.get(i),n=normals[i],c=m.c.get(i);q[i]=new float[]{(float)(v[0]*cs-v[2]*sn),v[1],(float)(v[0]*sn+v[2]*cs)};
   for(int j=0;j<2;j++){lo[j]=Math.min(lo[j],q[i][j]);hi[j]=Math.max(hi[j],q[i][j]);}
   float nx=(float)(n[0]*cs-n[2]*sn),nz=(float)(n[0]*sn+n[2]*cs),light=.42f+.58f*Math.max(0,nx*.30f+n[1]*.60f+nz*.74f);
   for(int j=0;j<3;j++)lit[i][j]=255f*(float)Math.pow(Math.max(0,Math.min(1,c[j]*light)),1/2.2);
  }
  float sc=410/Math.max(hi[0]-lo[0],hi[1]-lo[1]),cx=(lo[0]+hi[0])/2,cy=(lo[1]+hi[1])/2;
  for(float[] v:q){v[0]=size/2f+(v[0]-cx)*sc;v[1]=size/2f-(v[1]-cy)*sc;}
  for(int[] f:m.f){
   float[] a=q[f[0]],b=q[f[1]],c=q[f[2]];float den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);if(Math.abs(den)<1e-6f)continue;
   int xmin=Math.max(0,(int)Math.floor(Math.min(a[0],Math.min(b[0],c[0])))),xmax=Math.min(size-1,(int)Math.ceil(Math.max(a[0],Math.max(b[0],c[0]))));
   int ymin=Math.max(0,(int)Math.floor(Math.min(a[1],Math.min(b[1],c[1])))),ymax=Math.min(size-1,(int)Math.ceil(Math.max(a[1],Math.max(b[1],c[1]))));
   float[] ca=lit[f[0]],cb=lit[f[1]],cc=lit[f[2]];
   for(int y=ymin;y<=ymax;y++)for(int x=xmin;x<=xmax;x++){
    float u=((b[1]-c[1])*(x+.5f-c[0])+(c[0]-b[0])*(y+.5f-c[1]))/den,v=((c[1]-a[1])*(x+.5f-c[0])+(a[0]-c[0])*(y+.5f-c[1]))/den,w=1-u-v;
    if(u<-.00001f||v<-.00001f||w<-.00001f)continue;
    float z=u*a[2]+v*b[2]+w*c[2];int p=y*size+x;if(z<=depth[p])continue;depth[p]=z;
    pixels[p]=rgb(Math.max(0,Math.min(255,Math.round(u*ca[0]+v*cb[0]+w*cc[0]))),Math.max(0,Math.min(255,Math.round(u*ca[1]+v*cb[1]+w*cc[1]))),Math.max(0,Math.min(255,Math.round(u*ca[2]+v*cb[2]+w*cc[2]))));
   }
  }
  return pixels;
 }
}

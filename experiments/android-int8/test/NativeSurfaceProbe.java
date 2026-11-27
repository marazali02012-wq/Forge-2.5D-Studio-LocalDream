package com.forgestudio.mobileprobe;
import java.util.*;
public class NativeSurfaceProbe {
 public static void main(String[] args){
  int n=32;float r=1,iso=0;float[] d=new float[n*n*n];
  // Offset anisotropic ellipsoid catches axis swaps and winding errors.
  for(int x=0;x<n;x++)for(int y=0;y<n;y++)for(int z=0;z<n;z++){
   double a=(Engine.coord(x,n,r)-.12)/.35,b=(Engine.coord(y,n,r)+.15)/.48,c=(Engine.coord(z,n,r)-.24)/.60;
   d[(x*n+y)*n+z]=(float)(1-a*a-b*b-c*c);
  }
  Engine.Mesh m=NativeSurface.run(d,n,r,iso);float[] lo={99,99,99},hi={-99,-99,-99};Map<Long,Integer> edges=new HashMap<>();double volume=0;
  for(float[] v:m.v)for(int k=0;k<3;k++){lo[k]=Math.min(lo[k],v[k]);hi[k]=Math.max(hi[k],v[k]);}
  for(int[] f:m.f){volume+=Engine.dot(m.v.get(f[0]),Engine.cross(m.v.get(f[1]),m.v.get(f[2])))/6.0;for(int k=0;k<3;k++){long key=Engine.edgeKey(f[k],f[(k+1)%3]);edges.put(key,edges.getOrDefault(key,0)+1);}}
  for(int e:edges.values())if(e!=2)throw new AssertionError("open edge");
  double[] center={.12,-.15,.24},span={.70,.96,1.20};for(int k=0;k<3;k++)if(Math.abs((lo[k]+hi[k])/2-center[k])>.035||Math.abs(hi[k]-lo[k]-span[k])>.035)throw new AssertionError("axis error");
  if(Math.abs(volume-4*Math.PI/3*.35*.48*.60)>.02)throw new AssertionError("volume/winding error "+volume);
  System.out.println("MC33 ellipsoid PASS "+m.v.size()+" vertices "+m.f.size()+" faces volume "+volume);
 }
}

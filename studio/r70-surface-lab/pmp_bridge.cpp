#include <emscripten.h>
#include <pmp/surface_mesh.h>
#include <pmp/algorithms/smoothing.h>
#include <vector>
#include <cmath>
#include <algorithm>
extern "C" EMSCRIPTEN_KEEPALIVE
int forge_smooth(float* xyz, unsigned nv, const unsigned* idx,
                 unsigned ni, unsigned iterations, float maxmove) {
  if (!xyz || !idx || nv<3 || nv>150000 || ni<3 || ni%3 ||
      ni>900000 || iterations<1 || iterations>3 ||
      !std::isfinite(maxmove) || maxmove<=0) return -1;
  try {
    pmp::SurfaceMesh m;
    std::vector<pmp::Vertex> v; v.reserve(nv);
    for(unsigned i=0;i<nv;i++){
      for(unsigned k=0;k<3;k++) if(!std::isfinite(xyz[3*i+k])) return -2;
      v.push_back(m.add_vertex(pmp::Point(xyz[3*i],xyz[3*i+1],xyz[3*i+2])));
    }
    for(unsigned i=0;i<ni;i+=3){
      unsigned a=idx[i],b=idx[i+1],c=idx[i+2];
      if(a>=nv||b>=nv||c>=nv||a==b||a==c||b==c) return -3;
      auto f=m.add_triangle(v[a],v[b],v[c]);
      if(!f.is_valid()) return -4;
    }
    // Keep vertex IDs, open borders and all attributes intact.
    // Use uniform Laplacian for a bounded first experiment, not remeshing.
    pmp::explicit_smoothing(m,iterations,true);
    std::vector<float> out(xyz,xyz+3*nv);
    for(unsigned i=0;i<nv;i++){
      if(m.is_boundary(v[i])) continue;
      const auto p=m.position(v[i]);
      float dx=p[0]-xyz[3*i],dy=p[1]-xyz[3*i+1],dz=p[2]-xyz[3*i+2];
      float d=std::sqrt(dx*dx+dy*dy+dz*dz);
      if(!std::isfinite(d)) return -5;
      float s=d>maxmove ? maxmove/d : 1.f;
      out[3*i]+=s*dx;out[3*i+1]+=s*dy;out[3*i+2]+=s*dz;
    }
    std::copy(out.begin(),out.end(),xyz);
    return 0;
  } catch(...) {return -6;}
}

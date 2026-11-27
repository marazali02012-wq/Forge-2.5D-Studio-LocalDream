#include <emscripten.h>
#include <math.h>
#include <stddef.h>
#define GRD_ORTHOGONAL
#define USE_MM_RSQRT_SS 0
#define marching_cubes_33_c_implementation
#include "marching_cubes_33_c.h"
static surface* result=0;
EMSCRIPTEN_KEEPALIVE void forge_mc_clear(void){
  if(result){free_surface_memory(result);result=0;}
}
EMSCRIPTEN_KEEPALIVE int forge_mc_extract(float* data,unsigned nx,unsigned ny,unsigned nz,float iso){
  forge_mc_clear();
  if(!data||nx<2||ny<2||nz<2||nx>96||ny>96||nz>96||!isfinite(iso))return -1;
  for(size_t i=0;i<(size_t)nx*ny*nz;i++)if(!isfinite(data[i]))return -2;
  _GRD* g=grid_from_data_pointer(nx,ny,nz,data);
  if(!g)return -3;
  MC33* m=create_MC33(g);
  if(m){result=calculate_isosurface(m,iso);free_MC33(m);}
  free_memory_grd(g);
  return result?0:-4;
}
EMSCRIPTEN_KEEPALIVE unsigned forge_mc_vertices(void){return result?result->nV:0;}
EMSCRIPTEN_KEEPALIVE unsigned forge_mc_triangles(void){return result?result->nT:0;}
EMSCRIPTEN_KEEPALIVE const void* forge_mc_positions(void){return result?result->V:0;}
EMSCRIPTEN_KEEPALIVE const void* forge_mc_indices(void){return result?result->T:0;}

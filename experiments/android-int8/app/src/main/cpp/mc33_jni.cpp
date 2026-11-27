#include <jni.h>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <vector>
#include <stdexcept>
#include <memory>
#define GRD_ORTHOGONAL
#define USE_MM_RSQRT_SS 0
#define marching_cubes_33_c_implementation
#include "vendor/mc33/marching_cubes_33_c.h"

extern "C" JNIEXPORT jobjectArray JNICALL Java_com_forgestudio_mobileprobe_NativeSurface_extract(JNIEnv* env,jclass,jfloatArray input,jint n,jfloat radius,jfloat iso){
 try{
  if(!input||n<24||n>96||env->GetArrayLength(input)!=n*n*n||!std::isfinite(radius)||radius<=0||!std::isfinite(iso))throw std::runtime_error("invalid MC33 grid");
  std::vector<float> src(n*n*n),data(n*n*n);
  env->GetFloatArrayRegion(input,0,src.size(),src.data());if(env->ExceptionCheck())return nullptr;
  // Java density is z-fast; MC33 expects x-fast. Preserve coordinate handedness.
  for(int x=0;x<n;x++)for(int y=0;y<n;y++)for(int z=0;z<n;z++){
   float v=src[(x*n+y)*n+z];if(!std::isfinite(v))throw std::runtime_error("nonfinite density");data[(z*n+y)*n+x]=v;
  }
  std::vector<float>().swap(src);
  std::unique_ptr<_GRD,decltype(&free_memory_grd)> g(grid_from_data_pointer(n,n,n,data.data()),free_memory_grd);
  if(!g)throw std::runtime_error("MC33 grid allocation failed");
  for(int i=0;i<3;i++){g->r0[i]=-radius;g->d[i]=2.0*radius/(n-1);g->L[i]=2*radius;}g->periodic=0;
  std::unique_ptr<MC33,decltype(&free_MC33)> m(create_MC33(g.get()),free_MC33);
  if(!m)throw std::runtime_error("MC33 allocation failed");
  std::unique_ptr<surface,decltype(&free_surface_memory)> s(calculate_isosurface(m.get(),iso),free_surface_memory);
  if(!s||!s->nV||!s->nT||s->nV>1000000||s->nT>2000000)throw std::runtime_error("MC33 empty or excessive surface");
  std::vector<jint> indices(s->nT*3);std::vector<float> vertices(s->nV*3);
  for(unsigned i=0;i<s->nV;i++)for(int k=0;k<3;k++){float v=s->V[i][k];if(!std::isfinite(v)||fabs(v)>radius+1e-4)throw std::runtime_error("invalid vertex");vertices[i*3+k]=v;}
  for(unsigned i=0;i<s->nT;i++)for(int k=0;k<3;k++){auto v=s->T[i][k];if(v>=s->nV)throw std::runtime_error("invalid index");indices[i*3+k]=v;}
  // MC33 orientation varies with scalar convention. Orient each face using the
  // original field gradient (outward is toward decreasing density).
  auto sample=[&](double x,double y,double z){double q[3]={(x+radius)*(n-1)/(2*radius),(y+radius)*(n-1)/(2*radius),(z+radius)*(n-1)/(2*radius)};int a[3];double t[3];for(int k=0;k<3;k++){q[k]=std::fmax(0.0,std::fmin(double(n-1),q[k]));a[k]=std::min(n-2,(int)q[k]);t[k]=q[k]-a[k];}double sum=0;for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)sum+=data[((a[2]+k)*n+a[1]+j)*n+a[0]+i]*(i?t[0]:1-t[0])*(j?t[1]:1-t[1])*(k?t[2]:1-t[2]);return sum;};
  // Use one global winding decision so shared edges remain consistently oriented.
  double score=0,eps=radius/(n-1)*.25;
  for(unsigned i=0;i<s->nT;i++){const float *a=&vertices[indices[3*i]*3],*b=&vertices[indices[3*i+1]*3],*c=&vertices[indices[3*i+2]*3];double u[3],v[3],p[3];for(int k=0;k<3;k++){u[k]=b[k]-a[k];v[k]=c[k]-a[k];p[k]=(a[k]+b[k]+c[k])/3.0;}double norm[3]={u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]};double d[3]={sample(p[0]+eps,p[1],p[2])-sample(p[0]-eps,p[1],p[2]),sample(p[0],p[1]+eps,p[2])-sample(p[0],p[1]-eps,p[2]),sample(p[0],p[1],p[2]+eps)-sample(p[0],p[1],p[2]-eps)};for(int k=0;k<3;k++)score+=norm[k]*d[k];}
  if(score>0)for(unsigned i=0;i<s->nT;i++)std::swap(indices[3*i+1],indices[3*i+2]);
  jfloatArray pos=env->NewFloatArray(vertices.size());jintArray idx=env->NewIntArray(indices.size());if(!pos||!idx)return nullptr;
  env->SetFloatArrayRegion(pos,0,vertices.size(),vertices.data());env->SetIntArrayRegion(idx,0,indices.size(),indices.data());
  jclass object=env->FindClass("java/lang/Object");jobjectArray out=env->NewObjectArray(2,object,nullptr);if(!out)return nullptr;env->SetObjectArrayElement(out,0,pos);env->SetObjectArrayElement(out,1,idx);return out;
 }catch(const std::exception& e){if(!env->ExceptionCheck())env->ThrowNew(env->FindClass("java/lang/IllegalStateException"),e.what());return nullptr;}
}

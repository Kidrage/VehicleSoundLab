#include "startup_character/voice.h"
#include "startup_character/scene.h"
#include "spectral_texture/io.h"
#include <stdlib.h>
#ifdef _WIN32
#define SC_API __declspec(dllexport)
#else
#define SC_API
#endif
SC_API void *sc_open(const char *a,const char *b,const char *c,const double *env,double roughness,uint64_t seed){
    const char *names[SC_STAGES]={a,b,c};SfProfile *p=calloc(SC_STAGES,sizeof *p);
    const SfProfile *refs[SC_STAGES];ScVoice *v=NULL;unsigned k;
    if(!p)return NULL;
    for(k=0;k<SC_STAGES;++k){if(!sf_profile_load(names[k],p+k))goto done;refs[k]=p+k;}
    v=sc_create(refs,env,roughness,seed);
done:free(p);return v;
}
SC_API void sc_close(void *v){sc_destroy(v);}
SC_API unsigned sc_timeline_size(void){return sizeof(ScTimeline);}
SC_API int sc_scene_process(ScVoice *const v[3],const ScTimeline *t,uint64_t frame,const float *base,float *out,float *parts,unsigned frames){return sc_mix_scene(v,t,frame,base,out,parts,frames);}
SC_API int sc_configure_rotation(void *v,const CkProfile *p,uint64_t seed){return sc_set_rotation(v,p,seed);}
SC_API int sc_configure_ridges(void *v,const ScRidge *r,unsigned count,unsigned frames,double variation,double pitch,uint64_t seed){
    return sc_set_ridges(v,r,count,frames,variation,pitch,seed);
}
SC_API int sc_process(void *v,const double *progress,const int *gate,double strength,float *out,unsigned frames){
    unsigned n;if(!v||!progress||!gate||!out)return 0;
    for(n=0;n<frames;++n){double x[2];if(!sc_tick(v,progress[n],gate[n],strength,x))return 0;out[2*n]=(float)x[0];out[2*n+1]=(float)x[1];}
    return 1;
}
SC_API int sc_process_expression(void *v,const double *progress,const int *gate,const double *strength,
    const double *pitch,const double *core_gain,const double *texture_gain,float *out,unsigned frames){
    unsigned n;if(!v||!progress||!gate||!strength||!pitch||!core_gain||!texture_gain||!out)return 0;
    for(n=0;n<frames;++n){double x[2];if(!sc_tick_expression(v,progress[n],gate[n],strength[n],pitch[n],core_gain[n],texture_gain[n],x))return 0;out[2*n]=(float)x[0];out[2*n+1]=(float)x[1];}
    return 1;
}

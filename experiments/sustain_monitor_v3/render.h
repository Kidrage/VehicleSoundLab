#ifndef VSL_SUSTAIN_MONITOR_RENDER_H
#define VSL_SUSTAIN_MONITOR_RENDER_H
#include "voice.h"
#define SM_SEED UINT64_C(48271)
typedef struct {
    SdVoice source;
    double attenuation,target_attenuation,follow;
    unsigned onset,release;
    int stopping;
} SmRender;
int sm_render_init(SmRender *render,const SdProfile *model,int pitch,int detail,int attenuation_db);
int sm_render_set(SmRender *render,int pitch,int detail,int attenuation_db);
/* raw is the accepted fixed-phase DNA source; output adds common0.5 headroom,
   smoothed attenuation and device-only5ms onset/10ms stop envelopes. */
void sm_render_process(SmRender *render,float *raw,float *output,unsigned frames,int stop);
#endif

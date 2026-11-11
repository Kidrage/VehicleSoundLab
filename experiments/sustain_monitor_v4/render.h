#ifndef VSL_SUSTAIN_MONITOR_RENDER_H
#define VSL_SUSTAIN_MONITOR_RENDER_H
#include "voice.h"
#include "../../modules/low_rumble/voice.h"
#define SM_SEED UINT64_C(48271)
typedef struct {
    SdVoice source;
    LrVoice rumble;
    double attenuation,target_attenuation,follow;
    double dna_mix,dna_target,low_mix,low_target;
    unsigned onset,release;
    int stopping,mode;
} SmRender;
/* mode0 mix,1 DNA only,2 low only. Independent source states remain hot. */
int sm_render_init(SmRender *render,const SdProfile *dna,const LrProfile *low,int pitch,int detail,int db,int amount,int mode);
int sm_render_set(SmRender *render,int pitch,int detail,int db,int amount,int mode);
/* raw always contains unchanged DNA; low_raw is one mono source; out is stereo. */
void sm_render_process(SmRender *render,float *raw,float *low_raw,float *output,unsigned frames,int stop);
#endif

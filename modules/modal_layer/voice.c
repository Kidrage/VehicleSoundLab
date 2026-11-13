#include "voice.h"
#include <math.h>
#include <string.h>
int ml_voice_init(MlVoice *out,const MlProfile *p,uint64_t seed) {
    MlVoice v;unsigned n;double unused[2];
    if(!out||!ml_profile_valid(p))return 0;
    memset(&v,0,sizeof v);v.profile=p;
    if(!ms_voice_init(&v.modal,p->modal,p->modal_ratio,p->modal_gain)||
       !rdt_voice_init(&v.detail,p->detail,seed))return 0;
    for(n=0;n<p->detail->warmup_frames;++n)if(!rdt_voice_tick(&v.detail,0,unused,NULL))return 0;
    *out=v;return 1;
}
int ml_voice_tick(MlVoice *v,int gate,double envelope,MlFrame *out) {
    MlFrame f;unsigned c;
    if(!v||!v->profile||!out||(gate!=0&&gate!=1)||!isfinite(envelope)||envelope<0||envelope>8)return 0;
    if(gate!=v->gate) {
        v->gate=gate;v->remaining=gate?v->profile->attack_frames:v->profile->release_frames;
        v->step=(gate-v->position)/v->remaining;
    }
    if(v->remaining) {
        if(!--v->remaining)v->position=(double)v->gate;
        else v->position+=v->step;
    }
    if(!ms_voice_tick(&v->modal,f.modal)||!rdt_voice_tick(&v->detail,0,f.detail,NULL))return 0;
    f.weight=v->position*v->position*(3-2*v->position);f.keep=1-f.weight;
    for(c=0;c<2;++c) {
        f.detail[c]*=v->profile->detail_gain;f.raw[c]=f.modal[c]+f.detail[c];
        f.output[c]=f.raw[c]*(envelope*f.weight*v->profile->level_gain);
    }
    ++v->frame;*out=f;return 1;
}

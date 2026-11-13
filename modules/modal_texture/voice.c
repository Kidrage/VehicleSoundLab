#include "voice.h"
#include <math.h>
#include <stddef.h>
int mt_voice_init(MtVoice *out,const MsProfile *p,const MtProfile *m,
                  uint64_t seed,double ratio,double gain,double amount) {
    MtVoice v;
    if(!out||!p||!m||p->count!=m->count||
       !ms_voice_init(&v.source,p,ratio,gain)||!mt_envelope_init(&v.envelope,m,seed,amount))return 0;
    *out=v;return 1;
}
int mt_voice_set(MtVoice *v,double ratio,double gain,double amount) {
    if(!v||!v->source.profile||!v->envelope.profile||!isfinite(ratio)||ratio<.25||ratio>4||
       !isfinite(gain)||gain<0||gain>1||!isfinite(amount)||amount<0||amount>1)return 0;
    return ms_voice_set(&v->source,ratio,gain)&&mt_envelope_set(&v->envelope,amount);
}
int mt_voice_tick(MtVoice *v,double out[2]) {
    double gains[MT_MAX_MODES];
    if(!v||!v->source.profile||!v->envelope.profile||!out)return 0;
    if(!mt_envelope_tick(&v->envelope,gains))return 0;
    return ms_voice_tick_gains(&v->source,v->envelope.amount==0?NULL:gains,out);
}
int mt_voice_process(MtVoice *v,double *out,unsigned frames) {
    unsigned n;
    if(!v||!v->source.profile||!v->envelope.profile||(frames&&!out))return 0;
    for(n=0;n<frames;++n)if(!mt_voice_tick(v,out+2*n))return 0;
    return 1;
}

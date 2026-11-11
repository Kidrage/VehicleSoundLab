#include "voice.h"
#include "carrier.h"
#include <math.h>
#include <string.h>
int rm_voice_init(RmVoice *s,const SrProfile *p,const RmProfile *m,uint64_t seed,uint64_t motion_seed,
                   double pitch,double gain,double amount) {
    if(!s||!rm_profile_matches(m,p)||!isfinite(pitch)||pitch<.9||pitch>1.1||
       !isfinite(gain)||gain<0||gain>1||!isfinite(amount)||amount<0||amount>1)return 0;
    memset(s,0,sizeof *s);
    if(!sr_voice_init(&s->source,p,seed,pitch,gain)||!rm_envelope_init(&s->motion,m,motion_seed,amount))return 0;
    s->partials=p->partials;return 1;
}
int rm_voice_set(RmVoice *s,double pitch,double gain,double amount) {
    if(!s||!s->source.initialized||!s->motion.initialized||!isfinite(pitch)||pitch<.9||pitch>1.1||
       !isfinite(gain)||gain<0||gain>1||!isfinite(amount)||amount<0||amount>1)return 0;
    sr_voice_set(&s->source,pitch,gain);rm_envelope_set(&s->motion,amount);return 1;
}
int rm_voice_process(RmVoice *s,double *out,double *raw,unsigned frames) {
    unsigned n;
    if(!s||!s->source.initialized||!s->motion.initialized||(frames&&!out)||(raw&&raw==out))return 0;
    for(n=0;n<frames;++n) {
        SrVoice *v=&s->source;double g[SR_MAX_BANDS],base[2],shaped[2];unsigned c;
        v->pitch+=v->follow*(v->pitch_target-v->pitch);v->gain+=v->follow*(v->gain_target-v->gain);
        if(v->frame%64==0)sr_cloud_tune(&v->cloud,v->pitch);
        rm_envelope_tick(&s->motion,g);
        rm_carrier_tick(&v->cloud,s->partials,g,base,shaped,v->frame%1024==0);
        for(c=0;c<2;++c){out[2*n+c]=shaped[c]*v->gain;if(raw)raw[2*n+c]=base[c]*v->gain;}
        ++v->frame;
    }
    return 1;
}

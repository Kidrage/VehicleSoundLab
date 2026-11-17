#include "internal.h"
#include "drive/lifecycle.h"
#include <math.h>
int vs_engine_enable_start_flare(VsEngine *s){
    VsStartupResponse response;unsigned mask=(1u<<0)|(1u<<1)|(1u<<2)|(1u<<5);
    if(!s||s->generator.frame||s->event_pool.started||s->event_control.count||s->flare||
       s->owner.drive.lifecycle!=VSL_OFF)return 0;
    s->flare=sfl_create();if(!s->flare)return 0;
    /* One driver: silent 50ms preparation, then the selected 2.1s gesture. */
    response=*vsl_drive_lifecycle_profile(&s->owner.drive,s->generator.config.profile);
    response.crank_seconds=.05;response.catch_rise_seconds=.6;response.catch_settle_seconds=1.5;
    response.flare_rpm=2150;response.combustion_seconds=.16;
    s->owner.drive.lifecycle_response=response;s->owner.drive.lifecycle_override=1;
    s->event_control.available_mask&=~mask;s->flare_gain=1;
    return 1;
}
int vs_flare_sample(VsEngine *s,uint64_t frame){
    unsigned c,n=(unsigned)(frame-s->event_block_frame);double out[2],background;
    const VsStartupResponse *p;
    if(!s->flare)return 1;if(n>=VS_BLOCK_MAX)return 0;
    p=vsl_drive_lifecycle_profile(&s->owner.drive,s->generator.config.profile);
    if(!sfl_tick(s->flare,s->owner.drive.lifecycle,frame,p->catch_rise_seconds+p->catch_settle_seconds,
        s->flare_gain,out,&background))return 0;
    s->flare_background[n]=background;
    for(c=0;c<2;++c)s->flare_audio[2*n+c]=(float)out[c];
    return 1;
}
/* Apply the SAME captured foreground/background to every native bus and the
   electrical monitor before stem export. No host-only audition or second DSP
   path. Continuous generators keep advancing through the startup crossfade. */
void vs_flare_apply(VsEngine *s,unsigned frames,double gain){
    unsigned n,c,k;
    if(!s->flare)return;
    for(n=0;n<frames;++n){
        double w=s->flare_background[n];
        gain+=s->generator.follow*(s->adopted.mix.gain-gain);
        if(w==1&&s->flare_audio[2*n]==0&&s->flare_audio[2*n+1]==0)continue;
        for(c=0;c<2;++c){
            unsigned p=2*n+c;double flare=s->flare_audio[p];
            s->monitor[p]=(float)(s->monitor[p]*w+gain*flare);
            s->dna[p]=(float)(s->dna[p]*w);s->body[p]=(float)(s->body[p]*w);s->low[p]=(float)(s->low[p]*w);
            s->residual[p]=(float)(s->residual[p]*w);s->resonant[p]=(float)(s->resonant[p]*w);
            s->startup[p]=(float)(s->startup[p]*w+flare);
            s->catching[p]=(float)(s->catching[p]*w);s->added[p]=(float)(s->added[p]*w);
        }
        for(k=0;k<VSL_OBJECTS;++k)s->aux[n*VSL_OBJECTS+k]=(float)(s->aux[n*VSL_OBJECTS+k]*w);
        s->events[n]=(float)(s->events[n]*w);
        for(k=0;k<ES_VOICES;++k)s->event_voices[k][n]=(float)(s->event_voices[k][n]*w);
    }
}

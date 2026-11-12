#include "voice.h"
#include <math.h>
#include <string.h>
static int amount_valid(double x) { return isfinite(x)&&x>=0&&x<=1; }
int st_voice_init(StVoice *s,const StProfile *p,uint64_t seed,double amount) {
    if(!s||!st_profile_valid(p)||!amount_valid(amount))return 0;
    memset(s,0,sizeof *s);sr_cloud_init(&s->cloud,&p->spectrum,seed);sr_cloud_tune(&s->cloud,1);
    s->attack=1-exp(-1/(48000*p->attack_seconds));
    s->release=1-exp(-1/(48000*p->release_seconds));s->follow=1-exp(-1/(48000*.018));
    s->amount=s->amount_target=amount;s->initialized=1;return 1;
}
int st_voice_set(StVoice *s,int gate,double amount) {
    if(!s||!s->initialized||(gate!=0&&gate!=1)||!amount_valid(amount))return 0;
    s->gate=gate;s->amount_target=amount;return 1;
}
int st_voice_process(StVoice *s,double *out,double *raw,unsigned frames) {
    unsigned n,c;
    if(!s||!s->initialized||(frames&&!out)||(raw&&raw==out))return 0;
    for(n=0;n<frames;++n) {
        double x[2];
        sr_cloud_tick(&s->cloud,x,s->frame%1024==0);
        s->envelope+=(s->gate?s->attack:s->release)*(s->gate-s->envelope);
        s->amount+=s->follow*(s->amount_target-s->amount);
        for(c=0;c<2;++c) {
            if(raw)raw[2*n+c]=x[c];
            out[2*n+c]=x[c]*s->envelope*s->amount;
        }
        ++s->frame;
    }
    return 1;
}

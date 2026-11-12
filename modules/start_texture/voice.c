#include "voice.h"
#include <math.h>
#include <string.h>
static int amount_valid(double x) { return isfinite(x)&&x>=0&&x<=1; }
int st_voice_init(StVoice *s,const StProfile *p,uint64_t seed,double amount) {
    if(!s||!st_profile_valid(p)||!amount_valid(amount))return 0;
    memset(s,0,sizeof *s);sr_cloud_init(&s->cloud,&p->spectrum,seed);sr_cloud_tune(&s->cloud,1);
    s->attack=1-exp(-1/(48000*p->attack_seconds));
    s->release=1-exp(-1/(48000*p->release_seconds));s->follow=1-exp(-1/(48000*.018));
    s->amount=s->amount_target=amount;s->profile=*p;s->initialized=1;return 1;
}
int st_voice_position(StVoice *s,double x) {
    if(!s||!s->initialized||!amount_valid(x))return 0;
    s->position_target=x;return 1;
}
static void coefficients(StVoice *s) {
    unsigned b;double t=s->position;
    for(b=0;b<s->profile.spectrum.bands;++b) {
        const SrBand *a=&s->profile.spectrum.band[b],*z=&s->profile.finish.band[b];
        double l=(1-t)*a->power[0]+t*z->power[0],r=(1-t)*a->power[1]+t*z->power[1];
        double w=sqrt(a->power[0]*a->power[1]),v=sqrt(z->power[0]*z->power[1]);
        double re=(1-t)*a->coherence[0]*w+t*z->coherence[0]*v;
        double im=(1-t)*a->coherence[1]*w+t*z->coherence[1]*v;
        double left=sqrt(l),rr=left>0?re/left:0,ri=left>0?im/left:0;
        s->coefficient[b][0]=left;s->coefficient[b][1]=rr;s->coefficient[b][2]=ri;
        s->coefficient[b][3]=sqrt(fmax(0,r-rr*rr-ri*ri));
    }
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
        if(!s->profile.has_finish)sr_cloud_tick(&s->cloud,x,s->frame%1024==0);
        else {
            double unit[SR_MAX_BANDS][3];unsigned b;
            s->position+=s->follow*(s->position_target-s->position);
            if(s->frame%64==0)coefficients(s);
            sr_cloud_observe(&s->cloud,s->profile.spectrum.bands,s->profile.spectrum.partials,unit,s->frame%1024==0);
            x[0]=x[1]=0;
            for(b=0;b<s->profile.spectrum.bands;++b) {
                const double *v=s->coefficient[b];
                x[0]+=v[0]*unit[b][0];x[1]+=v[1]*unit[b][0]-v[2]*unit[b][1]+v[3]*unit[b][2];
            }
        }
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

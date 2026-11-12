#include "voice.h"
#include "envelope.h"
#include <math.h>
#include <string.h>
static int unit(double x){return isfinite(x)&&x>=0&&x<=1;}
int cb_voice_init(CbVoice *s,const CbProfile *p,double amount) {
    unsigned i;if(!s||!cb_profile_valid(p)||!unit(amount))return 0;
    memset(s,0,sizeof *s);s->profile=*p;s->amount=s->amount_target=amount;
    s->attack=1-exp(-1/(48000*p->attack_seconds));s->release=1-exp(-1/(48000*p->release_seconds));
    s->follow=1-exp(-1/(48000*.018));
    for(i=0;i<p->modes;++i)if(!cb_filter_init(s->filter+i,p->mode[i].hz,p->mode[i].q))return 0;
    s->initialized=1;return 1;
}
int cb_voice_set(CbVoice *s,int gate,double u,double amount) {
    if(!s||!s->initialized||(gate!=0&&gate!=1)||!unit(u)||!unit(amount))return 0;
    s->target=gate?cb_pulse(u,s->profile.rise_shape,s->profile.fall_shape):0;s->amount_target=amount;return 1;
}
int cb_voice_process(CbVoice *s,const double *input,double *delta,unsigned frames) {
    unsigned n,i,c;if(!s||!s->initialized||(frames&&(!input||!delta)))return 0;
    for(n=0;n<frames;++n) {
        double x[2]={input[2*n],input[2*n+1]},sum[2]={0};
        for(i=0;i<s->profile.modes;++i){double y[2];cb_filter_tick(s->filter+i,x,y);
            for(c=0;c<2;++c)sum[c]+=s->profile.mode[i].gain*y[c];}
        s->envelope=cb_follow(s->envelope,s->target,s->target>s->envelope?s->attack:s->release);
        s->amount=cb_follow(s->amount,s->amount_target,s->follow);
        for(c=0;c<2;++c)delta[2*n+c]=sum[c]*s->envelope*s->amount;
    }
    return 1;
}

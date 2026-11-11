#include "transfer.h"
#include "profile.h"
#include <math.h>
#include <string.h>
int vsl_phase_init(VslExhaustTransfer *s,double rate,int mode) {
    const VslPhaseProfile *p=vsl_phase_profile(mode);int c,k;memset(s,0,sizeof *s);
    if(!p||!isfinite(rate)||rate<16000||rate>192000)return 0;
    s->mode=mode;s->sample_rate=rate;s->eligible=1;
    s->delay_samples=(unsigned)(p->delay_seconds*rate+.5);if(s->delay_samples>=256)return 0;
    if(mode>=2)for(c=0;c<2;++c)for(k=0;k<3;++k)
        if(!vsl_allpass_init(&s->bank[c][k],rate,p->hz[k],p->q))return 0;
    return 1;
}
void vsl_phase_tick(VslExhaustTransfer *s,VslEngine *e,VslObjectFrame *o) {
    int c,k,eligible=e->smooth.profile==VSL_V10&&!e->dna.custom_count&&!e->target.pure_osc;
    if(eligible!=s->eligible) { int mode=s->mode;double rate=s->sample_rate;(void)vsl_phase_init(s,rate,mode);s->eligible=eligible; }
    if(!eligible||!s->mode)return;
    for(c=0;c<2;++c) {
        double x=o->sample[VSL_EXHAUST_L+c];
        if(s->mode==1) {
            s->delay[c][s->cursor]=x;x=s->delay[c][(s->cursor+256-s->delay_samples)%256];
        } else for(k=0;k<3;++k)x=vsl_allpass_tick(&s->bank[c][k],x);
        o->sample[VSL_EXHAUST_L+c]=x;
    }
    s->cursor=(s->cursor+1)%256;
}

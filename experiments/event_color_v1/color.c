#include "color.h"
#include "profile.h"
#include "drive/fueling.h"
#include <math.h>
#include <string.h>
static double unit(double x) { return fmax(0,fmin(1,x)); }
static void clear(VslEventColor *s) {
    const VslEventColorProfile *p=vsl_event_color_profile();int b,k;
    for(b=0;b<2;++b)for(k=0;k<2;++k)vsl_color_lowpass_init(&s->low[b][k],s->rate,p->split_hz[k]);
    memset(s->target,0,sizeof s->target);memset(s->smooth,0,sizeof s->smooth);
    memset(s->history,0,sizeof s->history);s->cursor=0;
}
int vsl_color_init(VslEventColor *s,double rate,double amount) {
    const VslEventColorProfile *p=vsl_event_color_profile();
    if(!isfinite(rate)||rate<16000||rate>192000||!isfinite(amount)||amount<0||amount>1)return 0;
    memset(s,0,sizeof *s);s->rate=rate;s->amount=amount;s->eligible=1;
    s->follow=1-exp(-1/(p->follow_seconds*rate));clear(s);return 1;
}
void vsl_color_tick(VslEventColor *s,const VslEngine *e,VslObjectFrame *o,const double main_pressure[2]) {
    const VslEventColorProfile *p=vsl_event_color_profile();const VslProfile *engine=vsl_profile(e->smooth.profile);
    int eligible=e->smooth.profile==VSL_V10&&!e->dna.custom_count&&!e->target.pure_osc&&e->target.combustion_variation;
    int fire=eligible&&vsl_fueling_allows_firing(&e->drive);int c,b,k;
    double depth=unit(e->smooth.irregularity/p->irregularity_reference);
    if(eligible!=s->eligible) {
        clear(s);memcpy(s->seen,e->character.events,sizeof s->seen);s->eligible=eligible;
    }
    /* Read the existing per-cylinder event; never draw RNG or retime a crank. */
    for(c=0;c<10;++c)if(s->seen[c]!=e->character.events[c]) {
        s->seen[c]=e->character.events[c];
        if(!fire) { ++s->denied_events;continue; }
        b=engine->bank[c];++s->events[b];
        s->target[b][0]=.65*e->character.energy[c]+.35*e->character.shape[c];
        s->target[b][1]=-.20*e->character.energy[c]+.80*e->character.shape[c];
    }
    for(b=0;b<2;++b) {
        double x=main_pressure[b]*e->excitation.firing;
        double low=vsl_color_lowpass_tick(&s->low[b][0],x),upper=vsl_color_lowpass_tick(&s->low[b][1],x);
        double modulation[2],delta;
        for(k=0;k<2;++k) {
            double desired=fire?s->target[b][k]:0;
            s->smooth[b][k]+=s->follow*(desired-s->smooth[b][k]);modulation[k]=s->smooth[b][k];
            if(b) {
                double delay=fmax(0,fmin(126,engine->bank_delay*s->rate)),f;unsigned n=(unsigned)floor(delay);
                f=delay-n;s->history[k][s->cursor]=modulation[k];
                modulation[k]=(1-f)*s->history[k][(s->cursor+128-n)%128]+f*s->history[k][(s->cursor+127-n)%128];
            }
            modulation[k]*=eligible?s->amount*depth:0;
            s->max_mod=fmax(s->max_mod,fabs(modulation[k]));
        }
        delta=p->mid_depth*modulation[0]*(upper-low)+p->high_depth*modulation[1]*(x-upper);
        if(s->amount&&eligible)o->sample[VSL_EXHAUST_L+b]+=delta;
        s->last[b]=x;s->last[2+b]=x+(s->amount&&eligible?delta:0);
        s->last[4+b*2]=modulation[0];s->last[5+b*2]=modulation[1];
    }
    s->cursor=(s->cursor+1)%128;
    if(s->tap_samples&&s->tap_frames<s->tap_capacity) {
        memcpy(s->tap_samples+s->tap_frames*8,s->last,sizeof s->last);++s->tap_frames;
    }
}

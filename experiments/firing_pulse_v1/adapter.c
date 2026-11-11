#include "adapter.h"
#include "profile.h"
#include "core/modules.h"
#include "profiles/firing.h"
#include "drive/fueling.h"
#include <math.h>
#include <string.h>
int fp_init(FpAdapter *s,double rate,int mode) {
    int b;if(!s||mode<0||mode>2)return 0;
    memset(s,0,sizeof *s);s->mode=mode;
    if(!fp_kernel_init(&s->kernel,rate))return 0;
    for(b=0;b<2;++b) {
        vsl_color_lowpass_init(&s->legacy_low[b],rate,fp_profile()->crossover_hz);
        vsl_color_lowpass_init(&s->pulse_low[b],rate,fp_profile()->crossover_hz);
    }
    return 1;
}
void fp_tick(FpAdapter *s,const VslEngine *e,VslObjectFrame *o,const double main_pressure[2]) {
    const FpProfile *p=fp_profile();const VslProfile *engine=vsl_profile(VSL_V10);
    double pulse[2],cycle=e->control.rpm/120,bank=cycle*5;
    int eligible=e->smooth.profile==VSL_V10&&!e->dna.custom_count&&!e->target.pure_osc&&e->target.combustion_variation;
    int c,b;
    if(eligible!=s->eligible) {
        int mode=s->mode;fp_init(s,e->sample_rate,mode);s->eligible=eligible;
        memcpy(s->previous,e->character.events,sizeof s->previous);
    }
    if(!eligible||s->mode==0)return;
    for(c=0;c<10;++c)if(s->previous[c]!=e->character.events[c]) {
        s->previous[c]=e->character.events[c];
        if(!vsl_fueling_allows_firing(&e->drive)||cycle<=0) { ++s->denied;continue; }
        {
            double angle=vsl_firing_degrees(VSL_V10,c,10)*2*VSL_PI/720;
            double distance=e->control.phase-angle,elapsed,slow,fast,gain,norm;
            double depth=s->mode==2?vsl_clamp(e->smooth.irregularity/.35,0,1):0;
            double duration=depth*e->character.shape[c],strength=depth*e->character.energy[c];
            double load=1.25-.25*vsl_clamp(e->voice.pull,0,1);
            if(distance<0)distance+=2*VSL_PI;
            elapsed=distance/(2*VSL_PI*cycle);
            slow=p->slow_seconds*load*(1+p->duration_spread*duration);
            fast=p->fast_seconds*load*(1-.5*p->duration_spread*duration);
            norm=sqrt(fp_kernel_energy(p->slow_seconds*load,p->fast_seconds*load)/fp_kernel_energy(slow,fast));
            gain=p->level*e->voice.dna_gain*e->smooth.dna*e->excitation.firing*
                sqrt(200/fmax(bank,1))*(1+.045*sin(c*1.7))*(1+p->energy_spread*strength)*norm;
            b=engine->bank[c];fp_kernel_strike(&s->kernel,b,elapsed,gain,slow,fast);++s->accepted[b];
        }
    }
    fp_kernel_tick(&s->kernel,pulse);
    {
        double delay=engine->bank_delay*e->sample_rate;unsigned n=(unsigned)floor(delay);
        double f=delay-n;
        s->delay[s->cursor]=pulse[1];
        pulse[1]=(1-f)*s->delay[(s->cursor+128-n)%128]+f*s->delay[(s->cursor+127-n)%128];
        s->cursor=(s->cursor+1)%128;
    }
    for(b=0;b<2;++b) {
        double x=main_pressure[b]*e->excitation.firing;
        double high=x-vsl_color_lowpass_tick(&s->legacy_low[b],x);
        double fresh=pulse[b]-vsl_color_lowpass_tick(&s->pulse_low[b],pulse[b]);
        double delta=p->blend*(fresh-high);
        s->last[b]=x;s->last[2+b]=fresh;s->last[4+b]=delta;
        s->max_delta=fmax(s->max_delta,fabs(delta));o->sample[VSL_EXHAUST_L+b]+=delta;
    }
}

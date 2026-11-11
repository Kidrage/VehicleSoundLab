#include "firing_source.h"
#include "modules.h"
#include "profiles/firing_source.h"
#include "profiles/firing.h"
#include "drive/fueling.h"
#include <math.h>
#include <string.h>

int vsl_firing_source_init(VslFiringSource *s,double rate) {
    const VslPulseProfile *p=vsl_pulse_profile();int b;
    if(!s||!isfinite(rate)||rate<16000||rate>192000)return 0;
    memset(s,0,sizeof *s);s->rate=rate;s->eligible=1;
    s->follow=1-exp(-1/(p->follow_seconds*rate));
    if(!vsl_pulse_kernel_init(&s->kernel,rate))return 0;
    for(b=0;b<2;++b) {
        vsl_color_lowpass_init(&s->original_low[b],rate,p->crossover_hz);
        vsl_color_lowpass_init(&s->pulse_low[b],rate,p->crossover_hz);
    }
    return 1;
}
void vsl_firing_source_tick(VslFiringSource *s,const VslEngine *e,VslObjectFrame *o,const double main_pressure[2]) {
    const VslPulseProfile *p=vsl_pulse_profile();const VslProfile *engine=vsl_profile(VSL_V10);
    double pulse[2],cycle=e->control.rpm/120,bank=cycle*5;
    int eligible=e->smooth.profile==VSL_V10&&!e->dna.custom_count&&!e->target.pure_osc&&e->target.combustion_variation;
    int fire=eligible&&vsl_fueling_allows_firing(&e->drive),c,b;
    double desired=eligible&&e->target.firing_source!=VSL_SOURCE_OSC?e->target.pulse_amount:0;
    s->mix+=s->follow*(desired-s->mix);
    if(desired==0&&s->mix<1e-12)s->mix=0;
    s->variation+=s->follow*((e->target.firing_source==VSL_SOURCE_VARIABLE?1.:0)-s->variation);
    if(eligible!=s->eligible) {
        /* Sync counters on template/bypass transitions: never replay missed events.
           Keep the response/filter/delay tails and fade their contribution. */
        memcpy(s->seen,e->character.events,sizeof s->seen);s->eligible=eligible;
    }
    for(c=0;c<10;++c)if(s->seen[c]!=e->character.events[c]) {
        s->seen[c]=e->character.events[c];
        if(!fire||cycle<=0) { ++s->denied;continue; }
        {
            double angle=vsl_firing_degrees(VSL_V10,c,10)*2*VSL_PI/720;
            double distance=e->control.phase-angle,elapsed,slow,fast,gain,norm;
            double depth=s->variation*vsl_clamp(e->smooth.irregularity/.35,0,1);
            double duration=depth*e->character.shape[c],strength=depth*e->character.energy[c];
            double load=1.25-.25*vsl_clamp(e->voice.pull,0,1);
            if(distance<0)distance+=2*VSL_PI;
            elapsed=distance/(2*VSL_PI*cycle);
            slow=p->slow_seconds*load*(1+p->duration_spread*duration);
            fast=p->fast_seconds*load*(1-.5*p->duration_spread*duration);
            norm=sqrt(vsl_pulse_kernel_energy(p->slow_seconds*load,p->fast_seconds*load)/vsl_pulse_kernel_energy(slow,fast));
            gain=p->level*e->voice.dna_gain*e->smooth.dna*e->excitation.firing*
                sqrt(200/fmax(bank,1))*(1+.045*sin(c*1.7))*(1+p->energy_spread*strength)*norm;
            b=engine->bank[c];vsl_pulse_kernel_strike(&s->kernel,b,elapsed,gain,slow,fast);++s->accepted[b];
        }
    }
    /* Hot state in OSC mode makes enabling independent of the UI/audio block size.
       There is no RNG, allocation, file I/O or separate crank clock here. */
    vsl_pulse_kernel_tick(&s->kernel,pulse);
    {
        double delay=engine->bank_delay*s->rate;unsigned n=(unsigned)floor(delay);double f=delay-n;
        s->delay[s->cursor]=pulse[1];
        pulse[1]=(1-f)*s->delay[(s->cursor+128-n)%128]+f*s->delay[(s->cursor+127-n)%128];
        s->cursor=(s->cursor+1)%128;
    }
    for(b=0;b<2;++b) {
        double x=main_pressure[b]*e->excitation.firing;
        double high=x-vsl_color_lowpass_tick(&s->original_low[b],x);
        double fresh=pulse[b]-vsl_color_lowpass_tick(&s->pulse_low[b],pulse[b]);
        double delta=p->blend*s->mix*(fresh-high);
        s->last[b]=x;s->last[2+b]=fresh;s->last[4+b]=delta;
        s->max_delta=fmax(s->max_delta,fabs(delta));
        if(s->mix>0)o->sample[VSL_EXHAUST_L+b]+=delta;
    }
}

#include "engine.h"
#include "modules.h"
#include "profiles/combustion.h"
#include "profiles/firing.h"
#include <math.h>

static double random_bipolar(uint32_t *seed) {
    uint32_t x=*seed;x^=x<<13;x^=x>>17;x^=x<<5;*seed=x;
    return (double)x/2147483648.-1;
}
static double wrapped(double phase) {
    phase=fmod(phase,2*VSL_PI);return phase<0?phase+2*VSL_PI:phase;
}
void vsl_combustion_init(VslEngine *e,uint32_t seed) {
    VslCombustion *v=&e->combustion;int i;
    v->stretch=v->gain[0]=v->gain[1]=1;
    v->seed[0]=seed^0x85ebca6bu;v->seed[1]=seed^0xc2b2ae35u;
    for(i=0;i<2;++i)if(!v->seed[i])v->seed[i]=1;
}
void vsl_combustion_tick(VslEngine *e) {
    VslCombustion *v=&e->combustion;
    const VslCombustionProfile *p=vsl_combustion_profile(e->smooth.profile);
    const VslProfile *engine=vsl_profile(e->smooth.profile);
    double cycle=e->control.rpm/120,bank=cycle*engine->cylinders/2;
    double pull=vsl_clamp(e->voice.pull,0,1),depth=e->smooth.irregularity;
    double enabled=p&&!e->dna.custom_count&&!e->smooth.pure_osc&&e->target.combustion_variation;
    double amplitude=0,arrival=0;int c,fire;
    if(!v->ready||v->profile!=e->smooth.profile) {
        v->profile=e->smooth.profile;v->mix=enabled?1:0;
        for(c=0;c<2;++c) { v->previous_cell[c]=0;v->amplitude[c]=v->arrival[c]=0; }
        v->ready=0;
    }
    v->mix+=(1-exp(-1/(e->sample_rate*(p?p->model_seconds:.025))))*(enabled-v->mix);
    if(fabs(v->mix-enabled)<1e-12)v->mix=enabled;
    /* Imported DNA/strict OSC retain their existing pitch and seed policy even
       when the switch is enabled. This also prevents stale phase on import. */
    if(!p||e->dna.custom_count||(e->smooth.pure_osc&&v->mix==0)) {
        v->mix=0;v->gain[0]=v->gain[1]=v->stretch=1;
        v->phase_delta[0]=v->phase_delta[1]=0;return;
    }
    amplitude=p->idle_amplitude+(p->loaded_amplitude-p->idle_amplitude)*pull;
    arrival=p->idle_arrival_seconds+(p->loaded_arrival_seconds-p->idle_arrival_seconds)*pull;
    /* Conservative nominal-frequency margin for this bounded phase warp.
       Smooth event windows still have weak higher sidebands; this is not a
       claim of mathematically bandlimited arbitrary FM. */
    v->stretch=1+VSL_PI*bank*arrival*depth*v->mix;
    fire=e->drive.combustion>0&&e->drive.fuel.command>0&&cycle>0;
    for(c=0;c<2;++c) {
        double phase=e->control.phase*engine->cylinders/2;
        double cell,window;
        if(c)phase-=2*VSL_PI*vsl_bank_offset_cycles(e->smooth.profile)+2*VSL_PI*bank*engine->bank_delay;
        phase=wrapped(phase);cell=wrapped(phase+VSL_PI);
        /* Draw at the pressure interval's midpoint, where the window and its
           first derivative are zero. The emitted pulse around phase 0 uses
           one event's coefficients with no step in the acoustic waveform. */
        if(fire&&(!v->ready||cell<v->previous_cell[c])) {
            v->amplitude[c]=p->event_memory*v->amplitude[c]+(1-p->event_memory)*random_bipolar(&v->seed[c]);
            v->arrival[c]=p->event_memory*v->arrival[c]+(1-p->event_memory)*random_bipolar(&v->seed[c]);
            ++v->events[c];
        }
        window=.5+.5*cos(phase);
        v->gain[c]=1+v->mix*depth*amplitude*v->amplitude[c]*window;
        /* Positive arrival variation is a delay, hence negative OSC phase. */
        v->phase_delta[c]=-2*VSL_PI*cycle*arrival*v->arrival[c]*window*depth*v->mix;
        v->previous_cell[c]=cell;
    }
    v->ready=1;
}

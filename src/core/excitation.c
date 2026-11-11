#include "engine.h"
#include "modules.h"
#include "profiles/firing.h"
#include "profiles/fueling.h"
#include <math.h>
#include <string.h>

static void configure(VslEngine *e) {
    VslExcitation *x=&e->excitation;
    const VslFuelingProfile *p=vsl_fueling_profile(e->smooth.profile);
    double omega=2*VSL_PI*p->cavity_hz/e->sample_rate;
    double alpha=sin(omega)/(2*p->cavity_q);
    memset(x,0,sizeof *x);x->profile=e->smooth.profile;x->firing=1;
    /* Constant-peak bandpass: finite motored pressure drives a cavity, whose
       stored energy can decay after fuel returns. No recorded IR is implied. */
    x->b0=alpha/(1+alpha);x->a1=-2*cos(omega)/(1+alpha);x->a2=(1-alpha)/(1+alpha);
}
void vsl_excitation_init(VslEngine *e) { configure(e); }
void vsl_excitation_tick(VslEngine *e,VslObjectFrame *o) {
    VslExcitation *x=&e->excitation;
    const VslFuelingProfile *p=vsl_fueling_profile(e->smooth.profile);
    const VslProfile *engine=vsl_profile(e->smooth.profile);
    /* Lifecycle envelopes already remove combustion outside RUNNING/CATCH.
       Hold the supply gate during shutdown: a previously cut engine must not
       briefly regain fired pressure when its ignition is switched off. */
    double command=e->drive.lifecycle==VSL_RUNNING?e->drive.fuel.command:
        (e->drive.lifecycle==VSL_CATCH?1:x->firing);
    double seconds=command>x->firing?p->attack_seconds:p->release_seconds;
    double bank=e->control.rpm*engine->cylinders/240;
    double rotation=e->voice.combustion;
    int side,n;
    if(x->profile!=e->smooth.profile)configure(e);
    x->firing+=(1-exp(-1/(seconds*e->sample_rate)))*(command-x->firing);
    if(fabs(x->firing-command)<1e-12)x->firing=command;
    x->pumping=1-x->firing;
    for(side=0;side<2;++side) {
        double phase=e->control.phase*engine->cylinders/2;
        double pulse=0,pressure,output;
        static const double harmonic[]={1,.32,.08};
        if(side)phase-=2*VSL_PI*vsl_bank_offset_cycles(e->smooth.profile)+2*VSL_PI*bank*engine->bank_delay;
        /* Smooth, zero-DC motored pulses: compression/expansion of air persists
           without combustion. Limit every harmonic at the actual sample rate. */
        for(n=1;n<=3;++n) {
            double guard=vsl_clamp((.46*e->sample_rate-n*bank)/(.04*e->sample_rate),0,1);
            pulse+=harmonic[n-1]*cos(n*phase)*guard;
        }
        pressure=pulse*x->pumping*rotation;
        output=x->b0*(pressure-x->x2[side])-x->a1*x->y1[side]-x->a2*x->y2[side];
        x->x2[side]=x->x1[side];x->x1[side]=pressure;
        x->y2[side]=x->y1[side];x->y1[side]=output;
        o->sample[VSL_EXHAUST_L+side]*=x->firing;
        o->sample[VSL_EXHAUST_L+side]+=output*p->pumping_level*e->smooth.pumping*e->smooth.dna;
    }
}

#include "engine.h"
#include "modules.h"
#include "profiles/firing.h"
#include "profiles/mechanical.h"
#include "drive/fueling.h"
#include <math.h>

static double random_bipolar(uint32_t *seed) {
    uint32_t x=*seed;x^=x<<13;x^=x>>17;x^=x<<5;*seed=x;
    return (double)x/2147483648.-1;
}
static void configure(VslEngine *e) {
    VslMechanical *m=&e->mechanical;
    const VslMechanicalProfile *p=vsl_mechanical_profile(e->smooth.profile);
    int i;for(i=0;i<VSL_MECHANICAL_MODES;++i)
        vsl_mode_init(&m->modes[i],p->modes[i].hz,p->modes[i].decay,e->sample_rate);
    m->profile=e->smooth.profile;m->previous_phase=e->control.phase;
    m->mix=e->target.mechanical_model?1:0;m->ready=1;
    m->rotating_strikes=m->fired_strikes=0;
}
static void strike(VslEngine *e,int fired,double elapsed,int cylinder) {
    VslMechanical *m=&e->mechanical;
    const VslMechanicalProfile *p=vsl_mechanical_profile(e->smooth.profile);
    double variation;
    double gain=fired?e->voice.mechanical_gain*e->excitation.firing:e->voice.mechanical_motion_gain;
    int i;
    /* A smoothed amplitude can still be positive after supply or lifecycle
       permission ends. It may scale a ringing response, never start a firing. */
    if(fired&&!vsl_fueling_allows_firing(&e->drive))return;
    if(gain<=1e-15)return;
    variation=1+p->cycle_spread*e->smooth.irregularity*random_bipolar(fired?&m->fired_seed:&m->rotating_seed);
    gain*=variation*(1+.025*sin(cylinder*1.7))*p->level;
    if(fired)++m->fired_strikes;else ++m->rotating_strikes;
    for(i=0;i<VSL_MECHANICAL_MODES;++i) {
        const VslMechanicalMode *mode=&p->modes[i];
        vsl_mode_strike(&m->modes[i],gain*(fired?mode->fired_gain:mode->rotating_gain),elapsed);
    }
}
double vsl_mechanical_modal_tick(VslEngine *e) {
    VslMechanical *m=&e->mechanical;
    const VslMechanicalProfile *shape=vsl_mechanical_profile(e->smooth.profile);
    const VslProfile *engine=vsl_profile(e->smooth.profile);
    double advance,output=0,cycle_hz=e->control.rpm/120;
    int i,c,kind;
    if(!m->ready||m->profile!=e->smooth.profile)configure(e);
    m->mix+=(1-exp(-1/(.020*e->sample_rate)))*((e->target.mechanical_model?1:0)-m->mix);
    if(fabs(m->mix-(e->target.mechanical_model?1:0))<1e-12)m->mix=e->target.mechanical_model?1:0;
    for(i=0;i<VSL_MECHANICAL_MODES;++i)(void)vsl_mode_tick(&m->modes[i]);
    advance=e->control.phase-m->previous_phase;if(advance<0)advance+=2*VSL_PI;
    if(e->smooth.profile!=VSL_SCIFI && cycle_hz>0 && e->drive.lifecycle!=VSL_OFF && e->drive.lifecycle!=VSL_READY) {
        for(c=0;c<engine->cylinders;++c)for(kind=0;kind<3;++kind) {
            double degrees=vsl_firing_degrees(e->smooth.profile,c,engine->cylinders);
            double angle,distance,elapsed;
            if(kind)degrees+=shape->rotating_offset[kind-1];
            angle=fmod(degrees,720)*2*VSL_PI/720;
            distance=angle-m->previous_phase;if(distance<=0)distance+=2*VSL_PI;
            if(distance>advance)continue;
            /* Exact crossing within this sample avoids quantising every hit to
               a sample edge. The stored resonator already advanced one tick. */
            elapsed=(advance-distance)/(2*VSL_PI*cycle_hz);
            strike(e,kind==0,elapsed,c);
        }
    }
    m->previous_phase=e->control.phase;m->stored_energy=0;
    for(i=0;i<VSL_MECHANICAL_MODES;++i) {
        VslMode *mode=&m->modes[i];output+=mode->real;
        m->stored_energy+=mode->real*mode->real+mode->imag*mode->imag;
    }
    return output;
}

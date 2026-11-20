#include "src/core/engine.h"
#include "src/core/modules.h"
#include "profiles/firing.h"
#include "profiles/mechanical.h"
#include "drive/fueling.h"
#include <math.h>
static float random_bipolar(uint32_t *seed) {
    uint32_t x=*seed;x^=x<<13;x^=x>>17;x^=x<<5;*seed=x;
    return (float)x/2147483648.f-1;
}
static void configure(VslEngine *e) {
    VslMechanical *m=&e->mechanical;
    const VslMechanicalProfile *p=vsl_mechanical_profile(e->smooth.profile);
    unsigned n;int i,c,kind;
    const VslProfile *engine=vsl_profile(e->smooth.profile);
    m->event_count=m->next_event=0;
    m->follow=1-expf(-1/(.020f*e->sample_rate));
    for(c=0;c<engine->cylinders;++c)for(kind=0;kind<3;++kind){
        float degrees=vsl_firing_degrees(e->smooth.profile,c,engine->cylinders);
        float angle;unsigned order=(unsigned)(3*c+kind);
        if(kind)degrees+=p->rotating_offset[kind-1];
        angle=fmodf(degrees,720)*2*VSL_PI/720;
        n=m->event_count++;
        while(n&&m->event_angle[n-1]>angle){m->event_angle[n]=m->event_angle[n-1];m->event_order[n]=m->event_order[n-1];--n;}
        m->event_angle[n]=angle;m->event_order[n]=order;
    }
    while(m->next_event<m->event_count&&m->event_angle[m->next_event]<=e->control.phase)++m->next_event;
    if(m->next_event==m->event_count)m->next_event=0;
    for(i=0;i<VSL_MECHANICAL_MODES;++i)
        vsl_mode_init(&m->modes[i],p->modes[i].hz,p->modes[i].decay,e->sample_rate);
    m->profile=e->smooth.profile;m->previous_phase=e->control.phase;
    m->mix=e->target.mechanical_model?1.f:0.f;m->ready=1;
    m->rotating_strikes=m->fired_strikes=0;
}
static void strike(VslEngine *e,int fired,float elapsed,int cylinder) {
    VslMechanical *m=&e->mechanical;
    const VslMechanicalProfile *p=vsl_mechanical_profile(e->smooth.profile);
    float variation;
    float gain=fired?e->voice.mechanical_gain*e->excitation.firing:e->voice.mechanical_motion_gain;
    int i;
    /* A smoothed amplitude can still be positive after supply or lifecycle
       permission ends. It may scale a ringing response, never start a firing. */
    if(fired&&!vsl_fueling_allows_firing(&e->drive))return;
    if(gain<=1e-15f)return;
    variation=1+p->cycle_spread*e->smooth.irregularity*random_bipolar(fired?&m->fired_seed:&m->rotating_seed);
    gain*=variation*(1+.025f*sinf(cylinder*1.7f))*p->level;
    if(fired)++m->fired_strikes;else ++m->rotating_strikes;
    for(i=0;i<VSL_MECHANICAL_MODES;++i) {
        const VslMechanicalMode *mode=&p->modes[i];
        vsl_mode_strike(&m->modes[i],gain*(fired?mode->fired_gain:mode->rotating_gain),elapsed);
    }
}
float vsl_mechanical_modal_tick(VslEngine *e) {
    VslMechanical *m=&e->mechanical;
    float advance,output=0,cycle_hz=e->control.rpm/120;
    int i;
    unsigned pending[36],count=0,j;float elapsed[36];
    if(!m->ready||m->profile!=e->smooth.profile)configure(e);
    m->mix+=m->follow*((e->target.mechanical_model?1.f:0.f)-m->mix);
    if(fabsf(m->mix-(e->target.mechanical_model?1.f:0.f))<1e-12f)m->mix=e->target.mechanical_model?1.f:0.f;
    for(i=0;i<VSL_MECHANICAL_MODES;++i)(void)vsl_mode_tick(&m->modes[i]);
    advance=e->control.phase-m->previous_phase;if(advance<0)advance+=2*VSL_PI;
    /* Only inspect the next sorted crossing. Retain the original sample-
       fractional strike time and cylinder/kind order for simultaneous hits. */
    for(j=0;j<m->event_count;++j){
        unsigned slot=m->next_event,rank=m->event_order[slot],at;
        float distance=m->event_angle[slot]-m->previous_phase;
        if(distance<=0)distance+=2*VSL_PI;
        if(distance>advance)break;
        m->next_event=(slot+1)%m->event_count;
        if(e->smooth.profile==VSL_SCIFI||cycle_hz<=0||e->drive.lifecycle==VSL_OFF||e->drive.lifecycle==VSL_READY)continue;
        at=count++;
        while(at&&pending[at-1]>rank){pending[at]=pending[at-1];elapsed[at]=elapsed[at-1];--at;}
        pending[at]=rank;elapsed[at]=(advance-distance)/(2*VSL_PI*cycle_hz);
    }
    for(j=0;j<count;++j)strike(e,pending[j]%3==0,elapsed[j],(int)(pending[j]/3));
    m->previous_phase=e->control.phase;m->stored_energy=0;
    for(i=0;i<VSL_MECHANICAL_MODES;++i) {
        VslMode *mode=&m->modes[i];output+=mode->real;
        m->stored_energy+=mode->real*mode->real+mode->imag*mode->imag;
    }
    return output;
}

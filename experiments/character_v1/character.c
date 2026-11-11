#include "character.h"
#include "core/modules.h"
#include "profiles/firing.h"
#include <math.h>
#include <string.h>
static VslCharacter *active;
static double random_bipolar(uint32_t *seed) {
    uint32_t x=*seed;x^=x<<13;x^=x>>17;x^=x<<5;*seed=x;return (double)x/2147483648.-1;
}
void vsl_character_init(VslCharacter *s,VslEngine *e,double pressure,double structure,uint32_t seed) {
    int c;memset(s,0,sizeof *s);s->engine=e;s->previous_phase=e->control.phase;
    s->amount_pressure=vsl_clamp(pressure,0,1);s->amount_structure=vsl_clamp(structure,0,1);
    s->energy_min=10;
    for(c=0;c<10;++c) { s->seed[c]=seed^((uint32_t)(c+1)*0x9e3779b9u)^0x27d4eb2du;if(!s->seed[c])s->seed[c]=1; }
    vsl_character_pressure_init(&s->pressure,e->sample_rate);
    vsl_character_structure_init(&s->structure,e->sample_rate);
}
void vsl_character_bind(VslCharacter *s) { active=s; }
unsigned vsl_character_events(const VslCharacter *s) {
    unsigned n=0;int c;for(c=0;c<10;++c)n+=s->events[c];return n;
}
void vsl_character_step(VslCharacter *s,VslEngine *e,VslObjectFrame *o) {
    const VslCharacterProfile *p=vsl_character_profile();
    const VslProfile *engine=vsl_profile(e->smooth.profile);
    double advance=e->control.phase-s->previous_phase,cycle=e->control.rpm/120.;
    int eligible=e->smooth.profile==VSL_V10&&!e->dna.custom_count;
    int fired=eligible&&!e->target.pure_osc&&
        (e->drive.lifecycle==VSL_RUNNING||e->drive.lifecycle==VSL_CATCH)&&
        e->drive.combustion>0&&e->drive.fuel.command>0&&e->excitation.firing>1e-8;
    int c;double pressure[2],base_mechanical=o->sample[VSL_MECHANICAL];
    if(advance<0)advance+=2*VSL_PI;
    vsl_character_pressure_advance(&s->pressure);vsl_character_structure_advance(&s->structure);
    if(fired&&cycle>0&&advance>0)for(c=0;c<10;++c) {
        double angle=vsl_firing_degrees(VSL_V10,c,10)*2*VSL_PI/720;
        double distance,elapsed,event_energy,shape,pressure_gain,structure_gain;
        /* Keep the existing right-bank acoustic travel convention separate
           from physical crank crossings; apply it to pressure arrival only. */
        distance=angle-s->previous_phase;if(distance<=0)distance+=2*VSL_PI;
        if(distance>advance)continue;
        elapsed=(advance-distance)/(2*VSL_PI*cycle);
        s->energy[c]=p->event_memory*s->energy[c]+(1-p->event_memory)*random_bipolar(&s->seed[c]);
        s->shape[c]=p->event_memory*s->shape[c]+(1-p->event_memory)*random_bipolar(&s->seed[c]);
        event_energy=(1+.04*sin(c*1.7))*(1+p->event_spread*e->smooth.irregularity*s->energy[c]);
        shape=s->shape[c]*e->smooth.irregularity;
        s->energy_min=fmin(s->energy_min,event_energy);s->energy_max=fmax(s->energy_max,event_energy);++s->events[c];
        pressure_gain=p->pressure_level*event_energy*e->voice.dna_gain*e->smooth.dna*e->excitation.firing;
        structure_gain=p->structure_level*event_energy*e->voice.dna_gain*(e->voice.mechanical_gain/.08)*e->excitation.firing;
        if(e->target.combustion_variation)
            vsl_character_pressure_strike(&s->pressure,engine->bank[c],pressure_gain,shape,elapsed);
        if(e->target.mechanical_model)
            vsl_character_structure_strike(&s->structure,structure_gain,shape,elapsed);
    }
    s->previous_phase=e->control.phase;
    vsl_character_pressure_read(&s->pressure,engine->bank_delay,pressure);
    for(c=0;c<3;++c)s->added[c]=0;
    if(!eligible)return;
    if(s->amount_pressure>0)for(c=0;c<2;++c) {
        s->added[c]=pressure[c]*s->amount_pressure*e->fade*e->combustion.mix;
        o->sample[VSL_EXHAUST_L+c]+=s->added[c];
    }
    if(s->amount_structure>0) {
        s->added[2]=s->amount_structure*e->mechanical.mix*(p->mechanical_boost*base_mechanical*e->fade+
            vsl_character_structure_read(&s->structure)*e->smooth.mechanical*e->smooth.noise*e->fade);
        o->sample[VSL_MECHANICAL]+=s->added[2];
    }
}
void vsl_character_hook(VslEngine *e,VslObjectFrame *o) {
    if(active&&active->engine==e)vsl_character_step(active,e,o);
}

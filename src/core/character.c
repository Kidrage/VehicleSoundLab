#include "character.h"
#include "response_shape.h"
#include "event_color.h"
#include "modules.h"
#include "profiles/firing.h"
#include "drive/fueling.h"
#include <math.h>
#include <string.h>
static double random_bipolar(uint32_t *seed) {
    uint32_t x=*seed;x^=x<<13;x^=x>>17;x^=x<<5;*seed=x;return (double)x/2147483648.-1;
}
void vsl_character_init(VslEngine *e,uint32_t seed) {
    VslCharacter *s=&e->character;int c;memset(s,0,sizeof *s);s->previous_phase=e->control.phase;
    s->energy_min=10;s->eligible=1;
    for(c=0;c<10;++c) { s->seed[c]=seed^((uint32_t)(c+1)*0x9e3779b9u)^0x27d4eb2du;if(!s->seed[c])s->seed[c]=1; }
    vsl_response_init(&e->response,e->sample_rate,0);
    vsl_color_init(&e->color,e->sample_rate,0);
    vsl_character_pressure_init(&s->pressure,e->sample_rate);
    vsl_character_structure_init(&s->structure,e->sample_rate);
}
unsigned vsl_character_events(const VslCharacter *s) {
    unsigned n=0;int c;for(c=0;c<10;++c)n+=s->events[c];return n;
}
void vsl_character_tick(VslEngine *e,VslObjectFrame *o) {
    VslCharacter *s=&e->character;const VslCharacterProfile *p=vsl_character_profile();
    const VslProfile *engine=vsl_profile(e->smooth.profile);
    double advance=e->control.phase-s->previous_phase,cycle=e->control.rpm/120.;
    int eligible=e->smooth.profile==VSL_V10&&!e->dna.custom_count;
    int fired=eligible&&!e->target.pure_osc&&
        vsl_fueling_allows_firing(&e->drive)&&e->excitation.firing>1e-8;
    int c;double pressure[2],base_mechanical=o->sample[VSL_MECHANICAL];
    s->amount_pressure=e->smooth.pressure_texture;s->amount_structure=e->smooth.structure_transfer;
    if(eligible!=s->eligible) {
        /* No stale factory ringing after changing template/import eligibility.
           RNG streams/counters remain instance-local and deterministic. */
        vsl_response_clear(&e->response);
        vsl_character_pressure_init(&s->pressure,e->sample_rate);
        vsl_character_structure_init(&s->structure,e->sample_rate);
        s->previous_phase=e->control.phase;s->eligible=eligible;advance=0;
    }
    if(advance<0)advance+=2*VSL_PI;
    e->response.amount=e->smooth.response_shape;vsl_response_begin(&e->response);
    vsl_character_pressure_advance(&s->pressure);vsl_character_structure_advance(&s->structure);
    if(fired&&cycle>0&&advance>0)for(c=0;c<10;++c) {
        double angle=vsl_firing_degrees(VSL_V10,c,10)*2*VSL_PI/720;
        double distance,elapsed,event_energy,shape,pressure_gain,structure_gain;
        distance=angle-s->previous_phase;if(distance<=0)distance+=2*VSL_PI;
        if(distance>advance)continue;
        elapsed=(advance-distance)/(2*VSL_PI*cycle);
        s->energy[c]=p->event_memory*s->energy[c]+(1-p->event_memory)*random_bipolar(&s->seed[c]);
        s->shape[c]=p->event_memory*s->shape[c]+(1-p->event_memory)*random_bipolar(&s->seed[c]);
        /* Dimensionless engineering event strength; not thermodynamic joules. */
        event_energy=(1+.04*sin(c*1.7))*(1+p->event_spread*e->smooth.irregularity*s->energy[c]);
        shape=s->shape[c]*e->smooth.irregularity;
        s->energy_min=fmin(s->energy_min,event_energy);s->energy_max=fmax(s->energy_max,event_energy);++s->events[c];
        pressure_gain=p->pressure_level*event_energy*e->voice.dna_gain*e->smooth.dna*e->excitation.firing;
        structure_gain=p->structure_level*event_energy*e->voice.dna_gain*(e->voice.mechanical_gain/.08)*e->excitation.firing;
        if(e->target.combustion_variation)
            vsl_response_pressure_strike(&e->response,e,&s->pressure,engine->bank[c],pressure_gain,shape,elapsed);
        if(e->target.mechanical_model)
            vsl_response_structure_strike(&e->response,e,&s->structure,structure_gain,shape,elapsed);
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
    vsl_response_apply(&e->response,e,o);
}

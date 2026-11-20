#include "core/response_shape.h"
#include "profiles/response_shape.h"
#include <math.h>
#include <string.h>
void vsl_response_clear(VslResponseShape *s) {
    const VslCharacterProfile *p=vsl_character_profile();
    vsl_response_kernel_init(&s->pressure[0],p->pressure,VSL_CHARACTER_PRESSURE_MODES,s->rate);
    vsl_response_kernel_init(&s->pressure[1],p->pressure,VSL_CHARACTER_PRESSURE_MODES,s->rate);
    vsl_response_kernel_init(&s->structure,p->structure,VSL_CHARACTER_STRUCTURE_MODES,s->rate);
    memset(s->pressure_history,0,sizeof s->pressure_history);s->cursor=0;
}
void vsl_response_init(VslResponseShape *s,float rate,float amount) {
    memset(s,0,sizeof *s);s->rate=rate;s->amount=fmaxf(0,fminf(1,amount));
    s->coordinate_min=1;s->coordinate_max=-1;vsl_response_clear(s);
}
void vsl_response_begin(VslResponseShape *s) {
    vsl_response_kernel_advance(&s->pressure[0]);vsl_response_kernel_advance(&s->pressure[1]);
    vsl_response_kernel_advance(&s->structure);
}
static float coordinate(VslResponseShape *s,const VslEngine *e,float shape) {
    float x=vsl_response_coordinate(e->control.rpm,e->voice.pull,shape,s->amount);
    s->coordinate_min=fminf(s->coordinate_min,x);s->coordinate_max=fmaxf(s->coordinate_max,x);return x;
}
void vsl_response_pressure_strike(VslResponseShape *s,VslEngine *e,VslCharacterPressure *native,
    int bank,float gain,float shape,float elapsed) {
    const VslCharacterProfile *p=vsl_character_profile();float weights[VSL_CHARACTER_PRESSURE_MODES];int i;
    for(i=0;i<VSL_CHARACTER_PRESSURE_MODES;++i)weights[i]=p->pressure[i].weight*(1+shape*(i-1)*p->shape_spread);
    vsl_response_kernel_strike(&s->pressure[bank],weights,gain,coordinate(s,e,shape),elapsed);++s->pressure_events;
    vsl_character_pressure_strike(native,bank,gain,shape,elapsed);
}
void vsl_response_structure_strike(VslResponseShape *s,VslEngine *e,VslCharacterStructure *native,
    float gain,float shape,float elapsed) {
    const VslCharacterProfile *p=vsl_character_profile();float weights[VSL_CHARACTER_STRUCTURE_MODES];int i;
    for(i=0;i<VSL_CHARACTER_STRUCTURE_MODES;++i)weights[i]=p->structure[i].weight*(1+.12f*shape);
    vsl_response_kernel_strike(&s->structure,weights,gain,coordinate(s,e,shape),elapsed);++s->structure_events;
    vsl_character_structure_strike(native,gain,shape,elapsed);
}
void vsl_response_apply(VslResponseShape *s,VslEngine *e,VslObjectFrame *o) {
    float pressure[2];int b;
    for(b=0;b<2;++b) {
        float delay=b?fminf(126,fmaxf(0,vsl_profile(e->smooth.profile)->bank_delay*s->rate)):0;
        unsigned integer=(unsigned)floorf(delay);float fraction=delay-integer;
        s->pressure_history[b][s->cursor]=vsl_response_kernel_read(&s->pressure[b]);
        pressure[b]=(1-fraction)*s->pressure_history[b][(s->cursor+128-integer)%128]+
            fraction*s->pressure_history[b][(s->cursor+127-integer)%128];
    }
    s->cursor=(s->cursor+1)%128;
    if(!s->amount||!e->character.eligible)return;
    if(e->character.amount_pressure>0)for(b=0;b<2;++b) {
        float added=pressure[b]*e->smooth.pressure_texture*e->fade*e->combustion.mix;
        o->sample[VSL_EXHAUST_L+b]+=added-e->character.added[b];
    }
    if(e->character.amount_structure>0) {
        /* Keep the existing explicit legacy mechanical boost on both sides.
           Only the extra fired structural response changes its shape. */
        float delta=vsl_response_kernel_read(&s->structure)-vsl_character_structure_read(&e->character.structure);
        o->sample[VSL_MECHANICAL]+=delta*e->smooth.structure_transfer*e->mechanical.mix*
            e->smooth.mechanical*e->smooth.noise*e->fade;
    }
}

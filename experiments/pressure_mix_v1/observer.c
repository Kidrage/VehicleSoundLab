#include "observer.h"
#include <inttypes.h>
void vsl_cf_strike(VslPressureObserver *s,VslEngine *e,VslCharacterPressure *p,
    int bank,double gain,double shape,double elapsed) {
    ++s->strikes;
    if(fprintf(s->events,"%" PRIu64 ",%d,%.17g,%.17g,%.17g\n",e->frame,bank,gain,shape,elapsed)<0)s->error=1;
    vsl_character_pressure_strike(p,bank,gain,shape,elapsed);
}
void vsl_cf_output(VslPressureObserver *s,VslEngine *e,VslObjectFrame *o) {
    uint64_t f=e->frame;int b;
    if(f>=s->frames) { s->error=1;return; }
    s->samples[3*f]=e->character.added[0];s->samples[3*f+1]=e->character.added[1];
    s->samples[3*f+2]=e->character.eligible&&e->character.amount_pressure>0?
        e->smooth.pressure_texture*e->fade*e->combustion.mix:0;
    if(s->replacement)for(b=0;b<2;++b)
        o->sample[VSL_EXHAUST_L+b]+=s->replacement[2*f+b]-e->character.added[b];
}

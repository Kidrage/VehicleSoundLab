#include "pressure.h"
#include <math.h>
#include <string.h>
void vsl_character_pressure_init(VslCharacterPressure *p,double rate) {
    const VslCharacterProfile *s=vsl_character_profile();int b,i;
    memset(p,0,sizeof *p);p->rate=rate;
    for(b=0;b<2;++b)for(i=0;i<VSL_CHARACTER_PRESSURE_MODES;++i)
        vsl_mode_init(&p->mode[b][i],s->pressure[i].hz,s->pressure[i].decay,rate);
}
void vsl_character_pressure_advance(VslCharacterPressure *p) {
    int b,i;for(b=0;b<2;++b)for(i=0;i<VSL_CHARACTER_PRESSURE_MODES;++i)(void)vsl_mode_tick(&p->mode[b][i]);
}
void vsl_character_pressure_strike(VslCharacterPressure *p,int bank,double gain,double shape,double elapsed) {
    const VslCharacterProfile *s=vsl_character_profile();int i;
    for(i=0;i<VSL_CHARACTER_PRESSURE_MODES;++i) {
        /* A common pressure event with bounded changes to its relative modal
           weights. Stored tails continue; no coefficient retune or reset. */
        double colour=1+shape*(i-1)*s->shape_spread;
        vsl_mode_strike(&p->mode[bank][i],gain*s->pressure[i].weight*colour,elapsed);
    }
}
void vsl_character_pressure_read(VslCharacterPressure *p,double right_delay,double output[2]) {
    int b,i;for(b=0;b<2;++b) {
        double x=0,delay=b?fmin(126,fmax(0,right_delay*p->rate)):0;
        unsigned n=(unsigned)floor(delay);double fraction=delay-n;
        for(i=0;i<VSL_CHARACTER_PRESSURE_MODES;++i)x+=p->mode[b][i].real;
        p->history[b][p->cursor]=x;
        output[b]=(1-fraction)*p->history[b][(p->cursor+128-n)%128]+
            fraction*p->history[b][(p->cursor+127-n)%128];
    }
    p->cursor=(p->cursor+1)%128;
}

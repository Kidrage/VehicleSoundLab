#include "internal.h"
#include <math.h>
void es_oscillator_init(EsOscillator *o,const EsMode *m,const EsRequest *r,double variation) {
    o->phase=m->phase;o->frequency=fmin(21000,m->hz*r->pitch*variation);
    o->end_hz=fmin(21000,m->end_hz*r->pitch*variation);
    o->amplitude=m->amplitude;
    o->decay=exp(-1/(ES_RATE*m->decay_seconds*r->decay));
    o->sweep_step=0;
}
double es_oscillator_tick(EsOscillator *o) {
    double x=sin(o->phase)*o->amplitude;
    o->phase+=2*ES_PI*o->frequency/ES_RATE;
    if(o->phase>=2*ES_PI)o->phase-=2*ES_PI;
    return x;
}

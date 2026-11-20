#include "modules/event_synth/internal.h"
#include <math.h>
#include "dsp/wave.h"
void es_oscillator_init(EsOscillator *o,const EsMode *m,const EsRequest *r,float variation) {
    o->phase=m->phase;o->frequency=fminf(21000,m->hz*r->pitch*variation);
    o->end_hz=fminf(21000,m->end_hz*r->pitch*variation);
    o->amplitude=m->amplitude;
    o->decay=expf(-1/(ES_RATE*m->decay_seconds*r->decay));
    o->sweep_step=0;
}
float es_oscillator_tick(EsOscillator *o) {
    float x=vsl_sine(o->phase)*o->amplitude;
    o->phase+=2*ES_PI*o->frequency/ES_RATE;
    if(o->phase>=2*ES_PI)o->phase-=2*ES_PI;
    return x;
}

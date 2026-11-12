#include "engine.h"
#include "modules.h"
#include <math.h>
static double random_unit(VslEvents *v) {
    v->seed^=v->seed<<13;v->seed^=v->seed>>17;v->seed^=v->seed<<5;
    return (double)v->seed/4294967296.;
}
void vsl_events_update(VslEngine *e) {
    VslEvents *v=&e->events;VslDrive *d=&e->drive;
    if(!e->target.ignition || d->lifecycle==VSL_OFF || !e->target.backfire) {
        v->remaining=0;v->overruns=d->overrun_events;v->shifts=d->shift_events;
    }
    if(v->starts!=d->start_events) { v->starts=d->start_events;v->starter_phase=v->starter_mod=0; }
    if(v->overruns!=d->overrun_events) {
        v->overruns=d->overrun_events;v->remaining=1+(int)(random_unit(v)*4);
        v->wait=.018;v->gain=d->overrun_strength*.16;
    }
    if(v->shifts!=d->shift_events) {
        v->shifts=d->shift_events;
        if(e->target.backfire && d->load>.25 && d->rpm>2000 && d->previous_gear>0 && d->shift_direction>0) {
            v->remaining=1;v->wait=.025;v->gain=.055;
        }
    }
}
void vsl_events_tick_parts(VslEngine *e,VslEventFrame *parts) {
    VslEvents *v=&e->events;double out=0,sr=e->sample_rate;
    if(v->remaining>0 && (v->wait-=1/sr)<=0) {
        v->envelope=v->gain;v->frequency=75+random_unit(v)*60;v->phase=0;
        --v->remaining;++v->hits;v->wait=.14+.06*random_unit(v);v->gain*=.75;
    }
    v->envelope*=exp(-1/(.035*sr));
    v->phase+=2*VSL_PI*v->frequency/sr;v->phase=fmod(v->phase,2*VSL_PI);
    out=v->envelope*(sin(v->phase)+.2*(2*random_unit(v)-1));
    {
        double crank=e->drive.lifecycle==VSL_CRANK?1:0;
        v->starter_envelope+=(1-exp(-1/((crank?.005:.018)*sr)))*(crank-v->starter_envelope);
        v->starter_phase=fmod(v->starter_phase+2*VSL_PI*85/sr,2*VSL_PI);
        v->starter_mod=fmod(v->starter_mod+2*VSL_PI*11/sr,2*VSL_PI);
        parts->starter=.045*(sin(v->starter_phase)+.25*sin(v->starter_phase*8))*(.55+.45*cos(v->starter_mod))*v->starter_envelope;
    }
    parts->transients=out;
}
double vsl_events_tick(VslEngine *e) {
    VslEventFrame p;vsl_events_tick_parts(e,&p);return p.transients+p.starter;
}

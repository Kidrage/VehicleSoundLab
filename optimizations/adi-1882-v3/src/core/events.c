#include "engine.h"
#include "modules.h"
#include <math.h>
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
static float event_cached_rate,event_decay,event_attack,event_release;
#endif
static float random_unit(VslEvents *v) {
    v->seed^=v->seed<<13;v->seed^=v->seed>>17;v->seed^=v->seed<<5;
    return (float)v->seed/4294967296.f;
}
void vsl_events_update(VslEngine *e) {
    VslEvents *v=&e->events;VslDrive *d=&e->drive;
    if(!e->target.ignition || d->lifecycle==VSL_OFF || !e->target.backfire) {
        v->remaining=0;v->overruns=d->overrun_events;v->shifts=d->shift_events;
    }
    if(v->starts!=d->start_events) { v->starts=d->start_events;v->starter_phase=v->starter_mod=0; }
    if(v->overruns!=d->overrun_events) {
        v->overruns=d->overrun_events;v->remaining=1+(int)(random_unit(v)*4);
        v->wait=.018f;v->gain=d->overrun_strength*.16f;
    }
    if(v->shifts!=d->shift_events) {
        v->shifts=d->shift_events;
        if(e->target.backfire && d->load>.25f && d->rpm>2000 && d->previous_gear>0 && d->shift_direction>0) {
            v->remaining=1;v->wait=.025f;v->gain=.055f;
        }
    }
}
void vsl_events_tick_parts(VslEngine *e,VslEventFrame *parts) {
    VslEvents *v=&e->events;float out=0,sr=e->sample_rate;
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
    if(event_cached_rate!=sr){
        event_decay=expf(-1/(.035f*sr));
        event_attack=1-expf(-1/(.005f*sr));
        event_release=1-expf(-1/(.018f*sr));event_cached_rate=sr;
    }
#endif
    if(v->remaining>0 && (v->wait-=1/sr)<=0) {
        v->envelope=v->gain;v->frequency=75+random_unit(v)*60;v->phase=0;
        --v->remaining;++v->hits;v->wait=.14f+.06f*random_unit(v);v->gain*=.75f;
    }
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
    v->envelope*=event_decay;
#else
    v->envelope*=expf(-1/(.035f*sr));
#endif
    v->phase+=2*VSL_PI*v->frequency/sr;v->phase=fmodf(v->phase,2*VSL_PI);
    out=v->envelope*(sinf(v->phase)+.2f*(2*random_unit(v)-1));
    {
        float crank=e->drive.lifecycle==VSL_CRANK?1.f:0.f;
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
        v->starter_envelope+=(crank?event_attack:event_release)*(crank-v->starter_envelope);
#else
        v->starter_envelope+=(1-expf(-1/((crank?.005f:.018f)*sr)))*(crank-v->starter_envelope);
#endif
        v->starter_phase=fmodf(v->starter_phase+2*VSL_PI*85/sr,2*VSL_PI);
        v->starter_mod=fmodf(v->starter_mod+2*VSL_PI*11/sr,2*VSL_PI);
        parts->starter=.045f*(sinf(v->starter_phase)+.25f*sinf(v->starter_phase*8))*(.55f+.45f*cosf(v->starter_mod))*v->starter_envelope;
    }
    parts->transients=out;
}
float vsl_events_tick(VslEngine *e) {
    VslEventFrame p;vsl_events_tick_parts(e,&p);return p.transients+p.starter;
}

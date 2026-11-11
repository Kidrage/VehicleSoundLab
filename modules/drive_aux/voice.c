#include "voice.h"
#include "motion.h"
#include "core/modules.h"
#include <math.h>
#include <string.h>
static int valid(const double *a) {
    int i;if(!a)return 0;
    for(i=0;i<DA_LAYERS;++i)if(!isfinite(a[i])||a[i]<0||a[i]>1)return 0;
    return 1;
}
int da_voice_set(DaVoice *v,const double a[DA_LAYERS]) {
    if(!v||!valid(a))return 0;
    memcpy(v->target,a,sizeof v->target);return 1;
}
int da_voice_init(DaVoice *v,VslEngine *e,const double a[DA_LAYERS]) {
    if(!v||!e||!valid(a)||e->sample_rate!=48000)return 0;
    memset(v,0,sizeof *v);v->follow=1-exp(-1/(.018*e->sample_rate));
    memcpy(v->amount,a,sizeof v->amount);memcpy(v->target,a,sizeof v->target);
    e->excitation.firing=0;return 1;
}
void da_voice_tick(DaVoice *v,VslEngine *e,VslObjectFrame *raw,VslObjectFrame *mixed) {
    static const int layer[VSL_OBJECTS]={-1,-1,DA_INTAKE,-1,DA_MECHANICAL,DA_AIR,DA_AIR,-1,DA_ROAD,DA_WIND};
    int i;
    memset(raw,0,sizeof *raw);memset(mixed,0,sizeof *mixed);
    da_motion_tick(e,v->follow);
    vsl_mechanical_tick(e,raw);
    vsl_nvh_tick(e,raw);
    /* Fired exhaust airflow decays with fuel supply; intake/motored rotation
       and road/wind remain independent. Ringing mechanical modes may decay. */
    raw->sample[VSL_AIR_L]*=e->excitation.firing;
    raw->sample[VSL_AIR_R]*=e->excitation.firing;
    for(i=0;i<DA_LAYERS;++i) {
        v->amount[i]+=v->follow*(v->target[i]-v->amount[i]);
        if(fabs(v->amount[i]-v->target[i])<1e-12)v->amount[i]=v->target[i];
    }
    for(i=0;i<VSL_OBJECTS;++i)if(layer[i]>=0)mixed->sample[i]=raw->sample[i]*v->amount[layer[i]];
}
void da_stereo(const VslObjectFrame *o,double x[2]) {
    double centre=.7071067811865475*(o->sample[VSL_INTAKE]+o->sample[VSL_MECHANICAL]+o->sample[VSL_ROAD]+o->sample[VSL_WIND]);
    x[0]=centre+o->sample[VSL_AIR_L];x[1]=centre+o->sample[VSL_AIR_R];
}

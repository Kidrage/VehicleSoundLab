#include "bridge.h"
#include <math.h>
#include <string.h>
static void read_gains(const VslVoicing *v,double *x) {
    x[0]=v->dna_gain;x[1]=v->body_gain;x[2]=v->intake_gain;x[3]=v->mechanical_gain;
    x[4]=v->air_gain;x[5]=v->high_gain;x[6]=v->mechanical_motion_gain;
}
static void write_gains(VslVoicing *v,const double *x) {
    v->dna_gain=x[0];v->body_gain=x[1];v->intake_gain=x[2];v->mechanical_gain=x[3];
    v->air_gain=x[4];v->high_gain=x[5];v->mechanical_motion_gain=x[6];
}
const char *vsl_gain_bridge_name(int i) {
    static const char *name[]={"exhaust","body","intake","mechanical","air","high_orders","mechanical_motion"};
    return i>=0&&i<VSL_BRIDGE_GAINS?name[i]:"invalid";
}
int vsl_gain_bridge_init(VslGainBridge *b,int enabled) {
    if(!b||(enabled!=0&&enabled!=1))return 0;
    memset(b,0,sizeof *b);b->enabled=enabled;return 1;
}
int vsl_gain_bridge_control(VslGainBridge *b,const VslVoicing *v,unsigned period) {
    if(!b||!v||!period)return 0;
    memcpy(b->start,b->current,sizeof b->start);read_gains(v,b->target);
    b->period=period;b->position=0;return 1;
}
void vsl_gain_bridge_audio(VslGainBridge *b,VslVoicing *v,float *pairs) {
    int i;
    if(b->position<b->period)++b->position;
    for(i=0;i<VSL_BRIDGE_GAINS;++i) {
        double x=b->period&&b->position<b->period?
            b->start[i]+(b->target[i]-b->start[i])*b->position/b->period:b->target[i];
        b->maximum_held_step[i]=fmax(b->maximum_held_step[i],fabs(b->target[i]-b->previous_held[i]));
        b->maximum_ramp_step[i]=fmax(b->maximum_ramp_step[i],fabs(x-b->previous_ramp[i]));
        b->previous_held[i]=b->target[i];b->previous_ramp[i]=x;b->current[i]=x;
        if(pairs) { pairs[2*i]=(float)b->target[i];pairs[2*i+1]=(float)x; }
    }
    if(b->enabled)write_gains(v,b->current);
}

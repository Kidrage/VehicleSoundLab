#include "modules.h"
#include "engine.h"
#include "profiles/firing.h"
#include <math.h>
static double noise(VslNvh *n) {
    uint32_t x=n->seed;x^=x<<13;x^=x>>17;x^=x<<5;n->seed=x;
    return (double)x/2147483648.-1;
}
void vsl_nvh_tick(VslEngine *e,VslObjectFrame *o) {
    double rate=e->sample_rate,a=1-exp(-2*VSL_PI*220/rate),b=1-exp(-2*VSL_PI*2400/rate);
    double h=1-exp(-2*VSL_PI*fmin(12500,rate*.4)/rate);int c;
    double pedal=vsl_clamp(fmax(0,e->control.throttle_delta)*.02,0,.15);
    e->nvh.env+=(1-exp(-1/(.045*rate)))*(pedal-e->nvh.env);
    for(c=0;c<2;++c) {
        double x=noise(&e->nvh),phase=e->control.phase*vsl_profile(e->smooth.profile)->cylinders/2+c*VSL_PI;
        if(e->smooth.profile==VSL_V10 && c) {
            double bank=e->control.rpm*10/240;
            phase=e->control.phase*5-2*VSL_PI*vsl_bank_offset_cycles(VSL_V10)-2*VSL_PI*bank*vsl_profile(VSL_V10)->bank_delay;
        }
        double pulse=pow(.5+.5*cos(phase),3);
        e->nvh.low[c]+=a*(x-e->nvh.low[c]);
        e->nvh.mid[c]+=b*(x-e->nvh.mid[c]);
        e->nvh.high[c]+=h*(x-e->nvh.high[c]);
        o->sample[VSL_AIR_L+c]=(e->nvh.high[c]-e->nvh.mid[c])*(.25+.75*pulse)*e->voice.air_gain*e->smooth.noise;
        o->sample[VSL_INTAKE]+=(e->nvh.mid[c]-e->nvh.low[c])*(.10+.28*e->voice.accel+1.2*e->nvh.env)*e->voice.intake_gain*e->smooth.intake;
    }
    {
        double speed=e->drive.speed_kph/160;
        o->sample[VSL_ROAD]=e->nvh.low[0]*.035*speed*e->smooth.noise;
        o->sample[VSL_WIND]=(e->nvh.mid[1]-e->nvh.low[1])*.025*speed*speed*e->smooth.noise;
    }
}

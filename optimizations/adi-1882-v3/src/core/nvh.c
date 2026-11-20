#include "modules.h"
#include "engine.h"
#include "profiles/firing.h"
#include <math.h>
static float noise(VslNvh *n) {
    uint32_t x=n->seed;x^=x<<13;x^=x>>17;x^=x<<5;n->seed=x;
    return (float)x/2147483648.f-1;
}
void vsl_nvh_tick(VslEngine *e,VslObjectFrame *o) {
    float rate=e->sample_rate,a=1-expf(-2*VSL_PI*220/rate),b=1-expf(-2*VSL_PI*2400/rate);
    float h=1-expf(-2*VSL_PI*fminf(12500,rate*.4f)/rate);int c;
    float pedal=vsl_clamp(fmaxf(0,e->control.throttle_delta)*.02f,0,.15f);
    e->nvh.env+=(1-expf(-1/(.045f*rate)))*(pedal-e->nvh.env);
    for(c=0;c<2;++c) {
        float x=noise(&e->nvh),phase=e->control.phase*vsl_profile(e->smooth.profile)->cylinders/2+c*VSL_PI;
        if(e->smooth.profile==VSL_V10 && c) {
            float bank=e->control.rpm*10/240;
            phase=e->control.phase*5-2*VSL_PI*vsl_bank_offset_cycles(VSL_V10)-2*VSL_PI*bank*vsl_profile(VSL_V10)->bank_delay;
        }
        float pulse=powf(.5f+.5f*cosf(phase),3);
        e->nvh.low[c]+=a*(x-e->nvh.low[c]);
        e->nvh.mid[c]+=b*(x-e->nvh.mid[c]);
        e->nvh.high[c]+=h*(x-e->nvh.high[c]);
        o->sample[VSL_AIR_L+c]=(e->nvh.high[c]-e->nvh.mid[c])*(.25f+.75f*pulse)*e->voice.air_gain*e->smooth.noise;
        o->sample[VSL_INTAKE]+=(e->nvh.mid[c]-e->nvh.low[c])*(.10f+.28f*e->voice.accel+1.2f*e->nvh.env)*e->voice.intake_gain*e->smooth.intake;
    }
    {
        float speed=e->drive.speed_kph/160;
        o->sample[VSL_ROAD]=e->nvh.low[0]*.035f*speed*e->smooth.noise;
        o->sample[VSL_WIND]=(e->nvh.mid[1]-e->nvh.low[1])*.025f*speed*speed*e->smooth.noise;
    }
}

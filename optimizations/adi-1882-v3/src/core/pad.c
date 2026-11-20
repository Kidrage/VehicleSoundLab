#include "modules.h"
#include <math.h>
float vsl_pad_tick(VslEngine *e) {
    float hz = e->control.rpm/60.0f, out=0;
    static const float ratios[3] = {.5f,1,2};
    static const float gains[3] = {.18f,.12f,.055f};
    int i;
    for(i=0;i<3;++i) {
        e->pad.phase[i] += 2*VSL_PI*hz*ratios[i]/e->sample_rate;
        if(e->pad.phase[i]>2*VSL_PI) e->pad.phase[i]-=2*VSL_PI;
        out += sinf(e->pad.phase[i])*gains[i];
    }
    return out*e->voice.body_gain;
}

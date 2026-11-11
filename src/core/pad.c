#include "modules.h"
#include <math.h>
double vsl_pad_tick(VslEngine *e) {
    double hz = e->control.rpm/60.0, out=0;
    static const double ratios[3] = {.5,1,2};
    static const double gains[3] = {.18,.12,.055};
    int i;
    for(i=0;i<3;++i) {
        e->pad.phase[i] += 2*VSL_PI*hz*ratios[i]/e->sample_rate;
        if(e->pad.phase[i]>2*VSL_PI) e->pad.phase[i]-=2*VSL_PI;
        out += sin(e->pad.phase[i])*gains[i];
    }
    return out*e->voice.body_gain;
}

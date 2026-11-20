#include "control.h"
#include <math.h>
static int range(float x,float max){return isfinite(x)&&x>=0&&x<=max;}
DchControl dch_default(void) {
    DchControl c={1,1,.5f,1,.35f,.25f,{1,1,1,1,1,1},{1,1,1,1,1,1}};return c;
}
int dch_control_valid(const DchControl *c) {
    unsigned s;if(!c||!range(c->line,2.6f)||!range(c->air,2.6f)||!range(c->motion,1.3f)||
        !range(c->idle_blend,1.3f)||!range(c->air_continuity,1.3f)||!range(c->pitch_follow,1.3f))return 0;
    for(s=0;s<DCH_STATES;++s)if(!range(c->line_state[s],2.6f)||!range(c->air_state[s],2.6f))return 0;
    return 1;
}

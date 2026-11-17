#include "control.h"
#include <math.h>
static int range(double x,double max){return isfinite(x)&&x>=0&&x<=max;}
DchControl dch_default(void) {
    DchControl c={1,1,.5,1,.35,.25,{1,1,1,1,1,1},{1,1,1,1,1,1}};return c;
}
int dch_control_valid(const DchControl *c) {
    unsigned s;if(!c||!range(c->line,2.6)||!range(c->air,2.6)||!range(c->motion,1.3)||
        !range(c->idle_blend,1.3)||!range(c->air_continuity,1.3)||!range(c->pitch_follow,1.3))return 0;
    for(s=0;s<DCH_STATES;++s)if(!range(c->line_state[s],2.6)||!range(c->air_state[s],2.6))return 0;
    return 1;
}

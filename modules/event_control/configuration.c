#include "api.h"
#include <math.h>
EcPolicy ec_policy_default(void) {
    EcPolicy p={1,3,.018,.095,.16,.72,1,0,.010,.008};return p;
}
static int range(double x,double lo,double hi){return isfinite(x)&&x>=lo&&x<=hi;}
int ec_policy_valid(const EcPolicy *p) {
    return p&&p->afterfire_min_count>=1&&p->afterfire_max_count<=4&&p->afterfire_min_count<=p->afterfire_max_count&&
        range(p->afterfire_delay_seconds,0,.65)&&range(p->afterfire_interval_min_seconds,.02,.65)&&
        range(p->afterfire_interval_max_seconds,p->afterfire_interval_min_seconds,.65)&&
        range(p->afterfire_repeat_gain,0,1.3)&&range(p->afterfire_probability,0,1)&&range(p->afterfire_cooldown_seconds,0,6.5)&&
        range(p->shift_delay_seconds,0,.325)&&range(p->crank_delay_seconds,0,.13);
}

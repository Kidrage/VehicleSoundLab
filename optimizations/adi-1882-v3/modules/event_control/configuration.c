#include "api.h"
#include <math.h>
EcPolicy ec_policy_default(void) {
    EcPolicy p={1,3,.018f,.095f,.16f,.72f,1,0,.010f,.008f};return p;
}
static int range(float x,float lo,float hi){return isfinite(x)&&x>=lo&&x<=hi;}
int ec_policy_valid(const EcPolicy *p) {
    return p&&p->afterfire_min_count>=1&&p->afterfire_max_count<=12&&p->afterfire_min_count<=p->afterfire_max_count&&
        range(p->afterfire_delay_seconds,0,.65f)&&range(p->afterfire_interval_min_seconds,.02f,.65f)&&
        range(p->afterfire_interval_max_seconds,p->afterfire_interval_min_seconds,.65f)&&
        range(p->afterfire_repeat_gain,0,1.3f)&&range(p->afterfire_probability,0,1)&&range(p->afterfire_cooldown_seconds,0,6.5f)&&
        range(p->shift_delay_seconds,0,.325f)&&range(p->crank_delay_seconds,0,.13f);
}

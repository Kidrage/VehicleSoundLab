#include "lifecycle.h"
#include <math.h>
/* Shared ENGINEERING start envelope, not identified car torque/RPM telemetry.
   Retain the previous overall 0.28 + 0.65 s policy; spend the first 0.20 s of
   CATCH building speed instead of jumping from starter speed to 1150 RPM.
   Shutdown/rolling-engine policy is retained pending a physical drivetrain. */
static const VslLifecycleProfile response = {
    .28,220,.07, .20,.45,1150,.06, .55,.12
};
const VslLifecycleProfile *vsl_lifecycle_profile(int profile) {
    (void)profile;return &response;
}
int vsl_lifecycle_profile_valid(const VslLifecycleProfile *p) {
#define RANGE(field,lo,hi) (isfinite(p->field)&&p->field>=lo&&p->field<=hi)
    return p&&RANGE(crank_seconds,.05,6.5)&&RANGE(crank_rpm,50,780)&&RANGE(crank_tau,.005,1.3)&&
        RANGE(catch_rise_seconds,.025,1.95)&&RANGE(catch_settle_seconds,.05,5.2)&&
        RANGE(flare_rpm,500,6500)&&RANGE(combustion_seconds,.005,2.6)&&
        p->combustion_seconds<=p->catch_rise_seconds+p->catch_settle_seconds&&
        RANGE(stopping_seconds,.05,6.5)&&RANGE(stopping_tau,.01,2.6);
#undef RANGE
}

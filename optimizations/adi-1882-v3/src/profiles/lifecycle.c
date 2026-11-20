#include "lifecycle.h"
#include <math.h>
/* Shared ENGINEERING start envelope, not identified car torque/RPM telemetry.
   Retain the previous overall 0.28 + 0.65 s policy; spend the first 0.20 s of
   CATCH building speed instead of jumping from starter speed to 1150 RPM.
   Shutdown/rolling-engine policy is retained pending a physical drivetrain. */
static const VslLifecycleProfile response = {
    .28f,220,.07f, .20f,.45f,1150,.06f, .55f,.12f
};
const VslLifecycleProfile *vsl_lifecycle_profile(int profile) {
    (void)profile;return &response;
}
int vsl_lifecycle_profile_valid(const VslLifecycleProfile *p) {
#define RANGE(field,lo,hi) (isfinite(p->field)&&p->field>=lo&&p->field<=hi)
    return p&&RANGE(crank_seconds,.05f,6.5f)&&RANGE(crank_rpm,50,780)&&RANGE(crank_tau,.005f,1.3f)&&
        RANGE(catch_rise_seconds,.025f,1.95f)&&RANGE(catch_settle_seconds,.05f,5.2f)&&
        RANGE(flare_rpm,500,6500)&&RANGE(combustion_seconds,.005f,2.6f)&&
        p->combustion_seconds<=p->catch_rise_seconds+p->catch_settle_seconds&&
        RANGE(stopping_seconds,.05f,6.5f)&&RANGE(stopping_tau,.01f,2.6f);
#undef RANGE
}

#include "lifecycle.h"
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

#ifndef VSL_LIFECYCLE_PROFILE_H
#define VSL_LIFECYCLE_PROFILE_H
typedef struct {
    float crank_seconds, crank_rpm, crank_tau;
    float catch_rise_seconds, catch_settle_seconds, flare_rpm, combustion_seconds;
    float stopping_seconds, stopping_tau;
} VslLifecycleProfile;
const VslLifecycleProfile *vsl_lifecycle_profile(int profile);
int vsl_lifecycle_profile_valid(const VslLifecycleProfile *profile);
#endif

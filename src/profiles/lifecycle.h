#ifndef VSL_LIFECYCLE_PROFILE_H
#define VSL_LIFECYCLE_PROFILE_H
typedef struct {
    double crank_seconds, crank_rpm, crank_tau;
    double catch_rise_seconds, catch_settle_seconds, flare_rpm, combustion_seconds;
    double stopping_seconds, stopping_tau;
} VslLifecycleProfile;
const VslLifecycleProfile *vsl_lifecycle_profile(int profile);
#endif

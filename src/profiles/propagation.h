#ifndef VSL_PROPAGATION_PROFILE_H
#define VSL_PROPAGATION_PROFILE_H
/* Engineering listener, not measured HRTF, cabin/exhaust IR or sound power. */
typedef struct {
    double speed_mps,ear_spacing_m,reference_distance_m,minimum_distance_m;
    double follow_seconds,shadow_hz,shadow_fraction;
} VslPropagationProfile;
const VslPropagationProfile *vsl_propagation_profile(void);
#endif

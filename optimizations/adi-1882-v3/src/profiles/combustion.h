#ifndef VSL_COMBUSTION_PROFILE_H
#define VSL_COMBUSTION_PROFILE_H
typedef struct {
    float idle_amplitude,loaded_amplitude;
    float idle_arrival_seconds,loaded_arrival_seconds;
    float event_memory,model_seconds;
} VslCombustionProfile;
const VslCombustionProfile *vsl_combustion_profile(int profile);
#endif

#ifndef VSL_PULSE_PROFILE_H
#define VSL_PULSE_PROFILE_H
typedef struct {
    double slow_seconds,fast_seconds,fast_weight;
    double level,blend,crossover_hz,energy_spread,duration_spread,follow_seconds;
} VslPulseProfile;
const VslPulseProfile *vsl_pulse_profile(void);
#endif

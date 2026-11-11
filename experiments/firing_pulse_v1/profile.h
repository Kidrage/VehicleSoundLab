#ifndef VSL_FIRING_PULSE_PROFILE_H
#define VSL_FIRING_PULSE_PROFILE_H
typedef struct {
    double slow_seconds,fast_seconds,fast_weight;
    double level,blend,crossover_hz,energy_spread,duration_spread;
} FpProfile;
const FpProfile *fp_profile(void);
#endif

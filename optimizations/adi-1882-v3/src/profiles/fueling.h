#ifndef VSL_FUELING_PROFILE_H
#define VSL_FUELING_PROFILE_H
typedef struct {
    float enter_above_idle, resume_above_idle;
    float close_pedal, reopen_pedal, coupled_delay, neutral_delay, resume_hold;
    float attack_seconds, release_seconds;
    float pumping_level, cavity_hz, cavity_q;
} VslFuelingProfile;
const VslFuelingProfile *vsl_fueling_profile(int profile);
#endif

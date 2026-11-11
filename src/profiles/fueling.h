#ifndef VSL_FUELING_PROFILE_H
#define VSL_FUELING_PROFILE_H
typedef struct {
    double enter_above_idle, resume_above_idle;
    double close_pedal, reopen_pedal, coupled_delay, neutral_delay, resume_hold;
    double attack_seconds, release_seconds;
    double pumping_level, cavity_hz, cavity_q;
} VslFuelingProfile;
const VslFuelingProfile *vsl_fueling_profile(int profile);
#endif

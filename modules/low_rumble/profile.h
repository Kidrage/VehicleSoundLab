#ifndef VSL_LOW_RUMBLE_PROFILE_H
#define VSL_LOW_RUMBLE_PROFILE_H
#define LR_MAX_OSCILLATORS 256
typedef struct {
    unsigned rate,count;
    double first_hz,step_hz,tau;
    double amplitude[LR_MAX_OSCILLATORS];
} LrProfile;
/* Transactional UTF-8 file loading, outside the audio callback. */
int lr_profile_load(const char *utf8_path,LrProfile *profile);
int lr_profile_valid(const LrProfile *profile);
#endif

#ifndef VSL_MODAL_SOURCE_PROFILE_H
#define VSL_MODAL_SOURCE_PROFILE_H
#define MS_MAX_MODES 64
#define MS_RATE 48000
typedef struct {
    double hz,amplitude[2],phase[2];
} MsMode;
typedef struct {
    unsigned rate,count;
    MsMode mode[MS_MAX_MODES];
} MsProfile;
/* Non-RT, no engine-specific frequency/order or clock assumptions. Profiles
   remain immutable and caller-owned for the entire voice lifetime. */
int ms_profile_valid(const MsProfile *profile);
#endif

#ifndef VSL_MODAL_SOURCE_PROFILE_H
#define VSL_MODAL_SOURCE_PROFILE_H
#include "dsp_support/config.h"
#ifndef MS_MAX_MODES
#define MS_MAX_MODES 64
#endif
#define MS_RATE 48000
typedef struct {
    float hz,amplitude[2],phase[2];
} MsMode;
typedef struct {
    unsigned rate,count;
    MsMode mode[MS_MAX_MODES];
} MsProfile;
/* Non-RT, no engine-specific frequency/order or clock assumptions. Profiles
   remain immutable and caller-owned for the entire voice lifetime. */
int ms_profile_valid(const MsProfile *profile);
#endif

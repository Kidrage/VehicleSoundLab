#ifndef VSL_START_TEXTURE_PROFILE_H
#define VSL_START_TEXTURE_PROFILE_H
#include "sound_residual/profile.h"
typedef struct {
    SrProfile spectrum; /* Observed stereo moments, not isolated physical sources. */
    double attack_seconds, release_seconds;
    int has_finish;
    SrProfile finish; /* Optional second PSD endpoint; same carrier bands. */
} StProfile;
int st_profile_valid(const StProfile *profile);
/* Non-RT and transactional. Does not load a waveform or a timed coefficient sequence. */
int st_profile_read(FILE *stream, StProfile *profile);
#endif

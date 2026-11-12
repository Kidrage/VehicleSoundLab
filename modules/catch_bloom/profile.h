#ifndef VSL_CATCH_BLOOM_PROFILE_H
#define VSL_CATCH_BLOOM_PROFILE_H
#include <stdio.h>
#define CB_MAX_MODES 4
typedef struct {double hz,q,gain;} CbMode;
typedef struct {
    unsigned modes;
    double rise_shape,fall_shape,attack_seconds,release_seconds;
    CbMode mode[CB_MAX_MODES];
} CbProfile;
int cb_profile_valid(const CbProfile *profile);
/* Non-RT transactional read. Observed mixed LF colour, not isolated structure. */
int cb_profile_read(FILE *stream,CbProfile *profile);
#endif

#ifndef VSL_SOUND_RESIDUAL_PROFILE_H
#define VSL_SOUND_RESIDUAL_PROFILE_H
#include <stdio.h>
#define SR_MAX_BANDS 16
#define SR_MAX_PARTIALS 32
typedef struct { double low,high,power[2],coherence[2]; } SrBand;
typedef struct { unsigned rate,bands,partials;SrBand band[SR_MAX_BANDS]; } SrProfile;
int sr_profile_valid(const SrProfile *profile);
/* Non-realtime, transactional ASCII read; file ownership stays with caller. */
int sr_profile_read(FILE *stream,SrProfile *profile);
#endif

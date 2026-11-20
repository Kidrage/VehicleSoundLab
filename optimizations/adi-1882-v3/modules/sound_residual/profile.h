#ifndef VSL_SOUND_RESIDUAL_PROFILE_H
#define VSL_SOUND_RESIDUAL_PROFILE_H
#include "dsp_support/config.h"
#include <stdio.h>
#ifndef SR_MAX_BANDS
#define SR_MAX_BANDS 16
#endif
#ifndef SR_MAX_PARTIALS
#define SR_MAX_PARTIALS 32
#endif
typedef struct { float low,high,power[2],coherence[2]; } SrBand;
typedef struct { unsigned rate,bands,partials;SrBand band[SR_MAX_BANDS]; } SrProfile;
int sr_profile_valid(const SrProfile *profile);
/* Non-realtime, transactional ASCII read; file ownership stays with caller. */
int sr_profile_read(FILE *stream,SrProfile *profile);
#endif

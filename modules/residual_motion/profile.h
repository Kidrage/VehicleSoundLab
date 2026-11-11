#ifndef VSL_RESIDUAL_MOTION_PROFILE_H
#define VSL_RESIDUAL_MOTION_PROFILE_H
#include "sound_residual/profile.h"
#define RM_MAX_FACTORS 8

typedef struct {
    unsigned bands,factors;
    double rho[RM_MAX_FACTORS];
    double low[SR_MAX_BANDS],high[SR_MAX_BANDS];
    double basis[SR_MAX_BANDS][RM_MAX_FACTORS];
} RmProfile;
/* Non-realtime; bounds guarantee a positive affine envelope for all seeds. */
int rm_profile_valid(const RmProfile *profile);
int rm_profile_matches(const RmProfile *motion,const SrProfile *source);
int rm_profile_read(FILE *stream,RmProfile *profile);
#endif

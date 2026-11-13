#ifndef VSL_SPECTRAL_MOTION_PROFILE_H
#define VSL_SPECTRAL_MOTION_PROFILE_H
#include "spectral_texture/profile.h"
#include "modal_texture/profile.h"
/* Generic composition, no recording/car/state identifiers. map[b]==0 keeps
   a band static; otherwise it selects motion row map[b]-1. Rows may be shared
   across bands. Every motion row must be used. */
typedef struct {
    const SfProfile *spectral;
    const MtProfile *motion;
    unsigned map[SF_MAX_BANDS];
} SpmProfile;
int spm_profile_valid(const SpmProfile *profile);
#endif

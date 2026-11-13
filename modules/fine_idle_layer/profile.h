#ifndef VSL_FINE_IDLE_LAYER_PROFILE_H
#define VSL_FINE_IDLE_LAYER_PROFILE_H
#include "modal_source/profile.h"
#include "modal_texture/profile.h"
#include "spectral_texture/profile.h"
typedef struct {
    const MsProfile *modal;const MtProfile *motion;const SfProfile *detail;
    double modal_ratio,modal_gain,detail_gain,level_gain;
    unsigned attack_frames,release_frames;
} FiProfile;
/* Non-RT independent source profile, not an RPM/common engine clock. */
int fi_profile_valid(const FiProfile *profile);
#endif

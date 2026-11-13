#ifndef VSL_MODAL_LAYER_PROFILE_H
#define VSL_MODAL_LAYER_PROFILE_H
#include "modal_source/profile.h"
#include "resonant_detail/profile.h"
typedef struct {
    const MsProfile *modal;
    const RdtProfile *detail;
    double modal_ratio,modal_gain,detail_gain,level_gain;
    unsigned attack_frames,release_frames;
} MlProfile;
/* Independent modes plus flat-envelope continuous resonators. No RPM,
   periodic clock, room, PCM, vehicle constants or source-state ownership. */
int ml_profile_valid(const MlProfile *profile);
#endif

#ifndef VSL_STATIONARY_BRIDGE_MODELS_H
#define VSL_STATIONARY_BRIDGE_MODELS_H
#include "atlas_drive/render.h"
typedef struct {
    SdProfile dna[5];
    RdtProfile detail[4];
    SaBank bank;
    DrsBank resonance;
    DrcBank recipe;
} SbmModels;
/* Non-RT transactional load. Four preserved anchors plus the one qualified
   bridge observation; rejected source windows never reach this bank. */
int sbm_models_load(SbmModels *out);
#endif

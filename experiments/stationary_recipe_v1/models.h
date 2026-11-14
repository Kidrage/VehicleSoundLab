#ifndef VSL_STATIONARY_RECIPE_MODELS_H
#define VSL_STATIONARY_RECIPE_MODELS_H
#include "atlas_drive/render.h"
typedef struct {
    SdProfile dna[4];
    RdtProfile detail[3];
    SaBank bank;
    DrsBank resonance;
    DrcBank recipe;
} SrmModels;
/* Non-RT. Original four DNA profiles, only three new supported detail fits.
   Output is committed only on success; caller retains storage until stopped. */
int srm_models_load(SrmModels *out);
#endif

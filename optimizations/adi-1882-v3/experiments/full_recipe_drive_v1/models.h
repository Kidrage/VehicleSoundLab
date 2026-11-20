#ifndef VSL_FULL_RECIPE_MODELS_H
#define VSL_FULL_RECIPE_MODELS_H
#include "drive_recipe/voice.h"
#include "resonant_detail_io/profile.h"
typedef struct {
    SdProfile dna,low;
    RdtProfile detail;
    SaBank bank;
    DrsBank resonance;
    DrcBank recipe;
} FrModels;
/* Existing frozen moving35 assets only; outside the audio callback. */
int fr_models_load(FrModels *models);
#endif

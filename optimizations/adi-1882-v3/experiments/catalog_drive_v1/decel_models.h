#ifndef VSL_CATALOG_DECEL_MODELS_H
#define VSL_CATALOG_DECEL_MODELS_H
#include "atlas_drive/render.h"
typedef struct {
    SdProfile dna;
    RvsProfile detail;
    SaBank bank;
    DrsBank resonance;
    DrcBank recipe;
} CdmModels;
/* Non-RT transactional loader. Copies frozen parameters without refitting;
   caller owns this storage until the preset takes its deep copy. */
int cdm_models_load(CdmModels *out);
#endif

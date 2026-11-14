#ifndef VSL_CATALOG_F3_MODELS_H
#define VSL_CATALOG_F3_MODELS_H
#include "atlas_drive/render.h"
typedef struct {
    SdProfile dna;
    RvsProfile detail;
    SaBank bank;
    DrsBank resonance;
    DrcBank recipe;
} F3mModels;
/* Non-RT, transactional. Frozen additive recipe; no PCM or state inference.
   The preset takes its own copy before this temporary storage is released. */
int f3m_models_load(F3mModels *out);
#endif

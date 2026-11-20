#ifndef VSL_CATALOG_F3_LOCAL_MODELS_H
#define VSL_CATALOG_F3_LOCAL_MODELS_H
#include "dna_atlas/bank.h"
typedef struct { SdProfile dna[3]; SaBank bank; } F3lModels;
/* NonRT, group0/1 are separate source observations, never combined.
   Owns all three frozen profiles; failure preserves the destination. */
int f3l_models_load(F3lModels *out,unsigned group);
#endif

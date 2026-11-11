#ifndef VSL_ATLAS_MONITOR_MODELS_H
#define VSL_ATLAS_MONITOR_MODELS_H
#include "dna_atlas/bank.h"
typedef struct { SdProfile profile[SA_MAX_ANCHORS];unsigned count; } AmModels;
/* Non-real-time, transactional; callers stop audio before committing candidate.
   Index0: A stationary rear. Index1: E high-RPM cabin. Neither has paired LF. */
int am_models_load(AmModels *destination,int index);
int am_models_bank(const AmModels *models,SaBank *bank);
#endif

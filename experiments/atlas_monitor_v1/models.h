#ifndef VSL_ATLAS_MONITOR_MODELS_H
#define VSL_ATLAS_MONITOR_MODELS_H
#include "dna_atlas/bank.h"
#include "residual_atlas/bank.h"
#include "start_texture/profile.h"
#include "catch_bloom/profile.h"
typedef struct { SdProfile profile[SA_MAX_ANCHORS];unsigned count;RaBank residual; } AmModels;
/* Non-real-time, transactional; callers stop audio before committing candidate.
   Index0: A stationary rear. Index1: E high-RPM cabin. Index2: A startup
   settling cabin, single anchor/no residual. None is full-state calibrated. */
int am_models_load(AmModels *destination,int index);
int am_models_bank(const AmModels *models,SaBank *bank);
int am_startup_load(StProfile *profile);
int am_catch_load(CbProfile *profile);
#endif

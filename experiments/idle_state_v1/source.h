#ifndef VSL_IDLE_STATE_SOURCE_H
#define VSL_IDLE_STATE_SOURCE_H
#include "../modal_idle_v1/models.h"
#include "modal_layer/voice.h"
#include "atlas_drive/source.h"
typedef struct {
    MlProfile profile;
    MlVoice voice;
    MlFrame latest;
    AdSourceProcessor processor;
    unsigned long long enabled_samples;
    int enabled,latest_gate;
    MlFrame *capture;unsigned capture_capacity,capture_count; /* Optional bounded host buffer. */
} IsSource;
/* Isolated study adapter: state gate only, ratio1 at all times. No actual F2
   RPM mapping. Source and model must stay at these addresses after init. */
int is_source_init(IsSource *source,const MiModels *models,uint64_t seed,int enabled);
#endif

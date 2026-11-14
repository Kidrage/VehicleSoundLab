#ifndef VSL_LAYER_MONITOR_SPLIT_H
#define VSL_LAYER_MONITOR_SPLIT_H
#include "layers.h"
typedef struct {
    double dna[2],body[2],residual[2],resonant[2],coherent[2],aux[2];
    double starter[2],catch_delta[2],added[2],event,gain;
    int fine_idle;
    double idle_modal[2],idle_detail[2],idle_scale;
} LmSources;
/* Trusted finite generated sources. Overwrites six stereo buses, applying
   existing master gain once; transport fade is the host's responsibility. */
void lm_split(const LmSources *sources,float output[LM_SAMPLES]);
#endif

#ifndef VSL_SUSTAIN_SOURCE_H
#define VSL_SUSTAIN_SOURCE_H
#include "model.h"
#include <stdint.h>
typedef struct {
    const SuModel *model;
    uint64_t rng,frame,updates;double spare;int has_spare;
    double phase,fraction,pitch,pitch_target,amount,amount_target,gain,gain_target,follow;
    double pc[SU_COMPONENTS],residual[SU_HARMONICS][4];
    double left[SU_HARMONICS][4],right[SU_HARMONICS][4];
} SuSource;
int su_init(SuSource *source,const SuModel *model,uint64_t seed,double pitch,double amount,double gain);
int su_set(SuSource *source,double pitch,double amount,double gain);
/* Generates requested duration indefinitely. No recording clock/loop, source
   waveform, allocation, file I/O, event trigger or state-dependent RPM claim. */
void su_process(SuSource *source,double *stereo,unsigned frames);
#endif

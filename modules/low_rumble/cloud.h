#ifndef VSL_LOW_RUMBLE_CLOUD_H
#define VSL_LOW_RUMBLE_CLOUD_H
#include "profile.h"
#include <stdint.h>
typedef struct {
    uint64_t rng,frame;
    double left[LR_MAX_OSCILLATORS][2],right[LR_MAX_OSCILLATORS][2];
    double rho,innovation,phase_first,phase_step,spare;
    unsigned position;
    int has_spare;
} LrCloud;
void lr_cloud_init(LrCloud *state,const LrProfile *profile,uint64_t seed);
double lr_cloud_sample(LrCloud *state,const LrProfile *profile,double pitch);
#endif

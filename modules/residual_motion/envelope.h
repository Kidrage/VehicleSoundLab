#ifndef VSL_RESIDUAL_MOTION_ENVELOPE_H
#define VSL_RESIDUAL_MOTION_ENVELOPE_H
#include "profile.h"
#include <stdint.h>
typedef struct {
    RmProfile profile; /* Owned; no loader lifetime in the audio callback. */
    uint64_t seed,frame;
    double left[RM_MAX_FACTORS],right[RM_MAX_FACTORS],innovation[RM_MAX_FACTORS];
    double amount,target,follow;
    int initialized;
} RmEnvelope;
int rm_envelope_init(RmEnvelope *envelope,const RmProfile *profile,uint64_t seed,double amount);
int rm_envelope_set(RmEnvelope *envelope,double amount);
/* Always advances, including amount0. Positive, common L/R gains per band. */
void rm_envelope_tick(RmEnvelope *envelope,double gain[SR_MAX_BANDS]);
#endif

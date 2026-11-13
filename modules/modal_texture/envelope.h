#ifndef VSL_MODAL_TEXTURE_ENVELOPE_H
#define VSL_MODAL_TEXTURE_ENVELOPE_H
#include "profile.h"
#include <stdint.h>
#define MT_RAMP_FRAMES 864
typedef struct {
    const MtProfile *profile; /* Immutable borrowed model; must outlive state. */
    uint64_t rng,frame;
    unsigned position,remaining;
    int has_spare;
    double spare,innovation_scale,amount,target,step;
    double variance[MT_MAX_MODES],left[MT_MAX_MODES],right[MT_MAX_MODES];
} MtEnvelope;
/* Non-RT; stationary initialization, no warmup timeline or allocation.
   Amount starts at the given value, permitting static offline/C comparison. */
int mt_envelope_init(MtEnvelope *state,const MtProfile *profile,uint64_t seed,double amount);
/* RT; finite18ms monotonic ramp. Same target does not restart the ramp. */
int mt_envelope_set(MtEnvelope *state,double amount);
/* RT. count positive gains, common L/R per mode. RNG advances even at zero.
   Invalid calls do not mutate. Output must not alias state/profile. */
int mt_envelope_tick(MtEnvelope *state,double *gains);
#endif

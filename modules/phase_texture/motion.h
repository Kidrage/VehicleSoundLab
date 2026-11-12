#ifndef VSL_PHASE_TEXTURE_MOTION_H
#define VSL_PHASE_TEXTURE_MOTION_H
#include <stdint.h>
#define PT_SPAN 256
#define PT_MARGIN 24
#define PT_NODES (PT_SPAN + 2 * PT_MARGIN + 1)
typedef struct {
    uint64_t rng, frame;
    double spare, last_seconds, filter[2][2];
    int has_spare;
    unsigned first, count, interval, sample;
    double nodes[PT_NODES], second[PT_NODES], cubic[PT_SPAN][4];
} PtMotion;
/* Non-RT initialization, independent RNG, fixed48kHz. A 20..70Hz stochastic
   control at187.5Hz, natural cubic interpolation, 2us scale/4us hard bound.
   These are engineering values, not measured crank jitter. */
void pt_motion_init(PtMotion *motion, uint64_t seed);
double pt_motion_tick(PtMotion *motion);
#endif

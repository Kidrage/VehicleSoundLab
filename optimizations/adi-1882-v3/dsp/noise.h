#ifndef VSL_COMPACT_NOISE_H
#define VSL_COMPACT_NOISE_H
#include <stdint.h>
/* Independent deterministic RNG; interpolated normal CDF with analytic tails. */
float vsl_normal(uint64_t *state);
#endif

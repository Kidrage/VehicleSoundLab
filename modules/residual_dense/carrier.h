#ifndef VSL_RESIDUAL_DENSE_CARRIER_H
#define VSL_RESIDUAL_DENSE_CARRIER_H
#include "sound_residual/oscillator.h"
#define RD_MAX_PARTIALS 256
#define RD_MAX_OSCILLATORS (2*SR_MAX_BANDS*RD_MAX_PARTIALS)

typedef struct { unsigned count;SrOscillator oscillator[RD_MAX_OSCILLATORS]; } RdCloud;
/* Spectral moments retain the existing SrProfile contract. Explicit counts
   are independent of its old partials field; no file/allocation in this API. */
int rd_counts_valid(const SrProfile *profile,const unsigned counts[SR_MAX_BANDS]);
int rd_cloud_init(RdCloud *cloud,const SrProfile *profile,const unsigned counts[SR_MAX_BANDS],uint64_t seed);
void rd_cloud_tune(RdCloud *cloud,double pitch);
void rd_cloud_tick(RdCloud *cloud,double stereo[2],int normalize);
#endif

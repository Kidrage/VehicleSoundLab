#ifndef VSL_RESIDUAL_MOTION_CARRIER_H
#define VSL_RESIDUAL_MOTION_CARRIER_H
#include "sound_residual/oscillator.h"
/* One carrier update, with both the old raw sum and per-band AM sum. */
void rm_carrier_tick(SrCloud *cloud,unsigned partials,const double *gain,
                     double raw[2],double shaped[2],int normalize);
#endif

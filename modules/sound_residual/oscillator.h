#ifndef VSL_SOUND_RESIDUAL_OSCILLATOR_H
#define VSL_SOUND_RESIDUAL_OSCILLATOR_H
#include "profile.h"
#include <stdint.h>
#define SR_MAX_OSCILLATORS (2*SR_MAX_BANDS*SR_MAX_PARTIALS)
typedef struct { double hz,re,im,cos_step,sin_step,left,right_re,right_im; } SrOscillator;
typedef struct { unsigned count;SrOscillator oscillator[SR_MAX_OSCILLATORS]; } SrCloud;
void sr_cloud_init(SrCloud *cloud,const SrProfile *profile,uint64_t seed);
void sr_cloud_tune(SrCloud *cloud,double pitch);
void sr_cloud_tick(SrCloud *cloud,double out[2],int normalize);
#endif

#ifndef VSL_VOICE_TYPES_H
#define VSL_VOICE_TYPES_H
#include "drive/types.h"
typedef enum {
    VSL_LAYER_EXHAUST, VSL_LAYER_BODY, VSL_LAYER_INTAKE,
    VSL_LAYER_MECHANICAL, VSL_LAYER_AIR, VSL_LAYER_HIGH, VSL_LAYERS
} VslLayer;
typedef struct {
    float combustion, idle, pull, overrun, release_mass;
    float dna_gain, body_gain, intake_gain, mechanical_gain, air_gain;
    float high_gain, accel, decel, catch_weight, tilt_delta, cutoff_ratio;
    float mechanical_motion_gain;
    float state_mix[VSL_OPERATING_COUNT], cut[VSL_LAYERS];
} VslVoicing;
#endif

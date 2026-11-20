#ifndef VSL_SPATIAL_TYPES_H
#define VSL_SPATIAL_TYPES_H
#include "dsp_support/config.h"
#include "objects.h"
#include "propagation_types.h"
#ifndef VSL_SPACE_DELAY
#define VSL_SPACE_DELAY 4096
#endif
typedef struct {
    float low[VSL_OBJECTS],cabin_low[VSL_OBJECTS],previous_input[VSL_MAX_CHANNELS],previous_output[VSL_MAX_CHANNELS];
    float reflection[2][VSL_SPACE_DELAY]; unsigned cursor;
    float gain[VSL_OBJECTS][VSL_MAX_CHANNELS], elevation[VSL_OBJECTS];
    float width, perspective;
    int channels, ready;
    VslPropagation propagation;
} VslSpatial;
#endif

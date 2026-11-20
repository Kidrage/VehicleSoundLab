#ifndef VSL_SPATIAL_TYPES_H
#define VSL_SPATIAL_TYPES_H
#include "objects.h"
#include "propagation_types.h"
#define VSL_SPACE_DELAY 4096
typedef struct {
    float low[VSL_OBJECTS],cabin_low[VSL_OBJECTS],previous_input[VSL_MAX_CHANNELS],previous_output[VSL_MAX_CHANNELS];
    float reflection[2][VSL_SPACE_DELAY]; unsigned cursor;
    float gain[VSL_OBJECTS][VSL_MAX_CHANNELS], elevation[VSL_OBJECTS];
    float width, perspective;
    int channels, ready;
    VslPropagation propagation;
} VslSpatial;
#endif

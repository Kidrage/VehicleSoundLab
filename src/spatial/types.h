#ifndef VSL_SPATIAL_TYPES_H
#define VSL_SPATIAL_TYPES_H
#include "objects.h"
#include "propagation_types.h"
#define VSL_SPACE_DELAY 4096
typedef struct {
    double low[VSL_OBJECTS],cabin_low[VSL_OBJECTS],previous_input[VSL_MAX_CHANNELS],previous_output[VSL_MAX_CHANNELS];
    double reflection[2][VSL_SPACE_DELAY]; unsigned cursor;
    double gain[VSL_OBJECTS][VSL_MAX_CHANNELS], elevation[VSL_OBJECTS];
    double width, perspective;
    int channels, ready;
    VslPropagation propagation;
} VslSpatial;
#endif

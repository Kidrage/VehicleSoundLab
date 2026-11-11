#ifndef VSL_PROPAGATION_TYPES_H
#define VSL_PROPAGATION_TYPES_H
#include "objects.h"
#define VSL_PATH_BUFFER 4096
#define VSL_PATH_TAPS 25
#define VSL_PATH_PHASES 256
#define VSL_PATH_LATENCY (VSL_PATH_TAPS/2+1)
enum { VSL_PATH_LEFT,VSL_PATH_RIGHT,VSL_PATH_CENTRE,VSL_PATH_COUNT };
typedef struct {
    float history[VSL_OBJECTS][VSL_PATH_BUFFER];
    double kernel[VSL_PATH_PHASES+1][VSL_PATH_TAPS];
    double delay[VSL_OBJECTS][VSL_PATH_COUNT],target_delay[VSL_OBJECTS][VSL_PATH_COUNT];
    double gain[VSL_OBJECTS][VSL_PATH_COUNT],target_gain[VSL_OBJECTS][VSL_PATH_COUNT];
    double shadow[VSL_OBJECTS][2],target_shadow[VSL_OBJECTS][2],shadow_low[VSL_OBJECTS][2];
    double centre_low[VSL_OBJECTS],mix,follow,shadow_coefficient;
    unsigned cursor,clamped_paths;
    int ready,kernel_ready;
} VslPropagation;
#endif

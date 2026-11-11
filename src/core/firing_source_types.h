#ifndef VSL_FIRING_SOURCE_TYPES_H
#define VSL_FIRING_SOURCE_TYPES_H
#include "pulse_kernel.h"
#include "event_split.h"
#include <stdint.h>

/* Modes describe the excitation; pure_osc remains the independent strict bypass. */
enum { VSL_SOURCE_OSC, VSL_SOURCE_FIXED, VSL_SOURCE_VARIABLE };
typedef struct {
    VslPulseKernel kernel;
    VslColorLowpass original_low[2],pulse_low[2];
    double rate,follow,mix,variation,delay[128],last[6],max_delta;
    unsigned seen[10],cursor;
    uint64_t accepted[2],denied;
    int eligible;
} VslFiringSource;
#endif

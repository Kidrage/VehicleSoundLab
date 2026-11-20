#ifndef VSL_RESPONSE_TYPES_H
#define VSL_RESPONSE_TYPES_H
#include "response_kernel.h"
#include <stdint.h>
typedef struct {
    VslResponseKernel pressure[2],structure;
    float pressure_history[2][128],rate,amount;
    unsigned cursor;
    uint64_t pressure_events,structure_events;
    float coordinate_min,coordinate_max;
} VslResponseShape;
#endif

#ifndef VSL_COMBUSTION_TYPES_H
#define VSL_COMBUSTION_TYPES_H
#include <stdint.h>
typedef struct {
    double previous_cell[2],amplitude[2],arrival[2];
    double phase_delta[2],gain[2],mix,stretch;
    uint32_t seed[2];
    unsigned events[2];
    int ready,profile;
} VslCombustion;
#endif

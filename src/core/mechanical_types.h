#ifndef VSL_MECHANICAL_TYPES_H
#define VSL_MECHANICAL_TYPES_H
#include "modal.h"
#include "profiles/mechanical.h"
#include <stdint.h>
typedef struct {
    VslMode modes[VSL_MECHANICAL_MODES];
    double previous_phase,mix,stored_energy;
    uint32_t rotating_seed,fired_seed;
    unsigned rotating_strikes,fired_strikes;
    int profile,ready;
} VslMechanical;
#endif

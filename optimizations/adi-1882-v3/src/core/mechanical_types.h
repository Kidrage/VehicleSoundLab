#ifndef VSL_MECHANICAL_TYPES_H
#define VSL_MECHANICAL_TYPES_H
#include "modal.h"
#include "profiles/mechanical.h"
#include <stdint.h>
typedef struct {
    VslMode modes[VSL_MECHANICAL_MODES];
    float previous_phase,mix,stored_energy;
    uint32_t rotating_seed,fired_seed;
    unsigned rotating_strikes,fired_strikes;
    int profile,ready;
    float event_angle[36],follow;
    unsigned event_order[36],event_count,next_event;
} VslMechanical;
#endif

#ifndef VSL_EVENT_COLOR_TYPES_H
#define VSL_EVENT_COLOR_TYPES_H
#include "event_split.h"
#include <stdint.h>
typedef struct {
    VslColorLowpass low[2][2];
    double rate,amount,follow,target[2][2],smooth[2][2],history[2][128];
    double last[8],max_mod;
    unsigned seen[10],cursor;int eligible;
    uint64_t events[2],denied_events;
} VslEventColor;
#endif

#ifndef VSL_EVENTS_H
#define VSL_EVENTS_H
#include <stdint.h>
typedef struct {
    uint32_t seed;
    unsigned starts,shifts,overruns,hits;
    int remaining;
    double wait,envelope,phase,frequency,gain,noise_low;
    double starter_phase,starter_mod,starter_envelope;
} VslEvents;
typedef struct {double transients,starter;} VslEventFrame;
#endif

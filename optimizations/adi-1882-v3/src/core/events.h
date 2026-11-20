#ifndef VSL_EVENTS_H
#define VSL_EVENTS_H
#include <stdint.h>
typedef struct {
    uint32_t seed;
    unsigned starts,shifts,overruns,hits;
    int remaining;
    float wait,envelope,phase,frequency,gain,noise_low;
    float starter_phase,starter_mod,starter_envelope;
} VslEvents;
typedef struct {float transients,starter;} VslEventFrame;
#endif

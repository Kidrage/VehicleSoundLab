#ifndef VSL_PRESSURE_OBSERVER_H
#define VSL_PRESSURE_OBSERVER_H
#include "core/engine.h"
#include "session/take.h"
#include <stdio.h>
/* Offline only: these buffers contain our own procedural pressure response.
   No reference-recording playback or observer code enters the native core. */
typedef struct {
    FILE *events;
    double *samples;              /* added L, added R, post-response gain */
    const double *replacement;   /* optional replacement added L/R */
    uint64_t frames,strikes;
    unsigned resets;
    int error;
} VslPressureObserver;
void vsl_cf_strike(VslPressureObserver *observer,VslEngine *e,
    VslCharacterPressure *pressure,int bank,double gain,double shape,double elapsed);
void vsl_cf_output(VslPressureObserver *observer,VslEngine *e,VslObjectFrame *objects);
void vsl_cf_character_tick(VslEngine *e,VslPressureObserver *observer,VslObjectFrame *objects);
int vsl_cf_process(VslEngine *e,VslPressureObserver *observer,float *out,unsigned frames,int channels,float *stems);
unsigned vsl_cf_take(VslTakePlayer *player,VslEngine *e,VslPressureObserver *observer,
    float *out,unsigned frames,int channels,float *stems);
#endif

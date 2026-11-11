#ifndef VSL_RESPONSE_SHAPE_H
#define VSL_RESPONSE_SHAPE_H
#include "kernel.h"
#include "core/engine.h"
#include "session/take.h"
typedef struct {
    VslResponseKernel pressure[2],structure;
    double pressure_history[2][128],rate,amount;
    unsigned cursor;
    uint64_t pressure_events,structure_events;
    double coordinate_min,coordinate_max;
} VslResponseShape;
void vsl_response_init(VslResponseShape *s,double rate,double amount);
void vsl_response_clear(VslResponseShape *s);
void vsl_response_begin(VslResponseShape *s);
void vsl_response_pressure_strike(VslResponseShape *s,VslEngine *e,VslCharacterPressure *native,
    int bank,double gain,double shape,double elapsed);
void vsl_response_structure_strike(VslResponseShape *s,VslEngine *e,VslCharacterStructure *native,
    double gain,double shape,double elapsed);
void vsl_response_apply(VslResponseShape *s,VslEngine *e,VslObjectFrame *objects);
void vsl_response_character_tick(VslEngine *e,VslResponseShape *response,VslObjectFrame *objects);
int vsl_response_process(VslEngine *e,VslResponseShape *response,float *out,unsigned frames,int channels,float *stems);
unsigned vsl_response_take(VslTakePlayer *player,VslEngine *e,VslResponseShape *response,
    float *out,unsigned frames,int channels,float *stems);
#endif

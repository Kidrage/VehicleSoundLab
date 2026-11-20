#ifndef VSL_RESPONSE_SHAPE_H
#define VSL_RESPONSE_SHAPE_H
#include "engine.h"
void vsl_response_init(VslResponseShape *s,float rate,float amount);
void vsl_response_clear(VslResponseShape *s);
void vsl_response_begin(VslResponseShape *s);
void vsl_response_pressure_strike(VslResponseShape *s,VslEngine *e,VslCharacterPressure *native,
    int bank,float gain,float shape,float elapsed);
void vsl_response_structure_strike(VslResponseShape *s,VslEngine *e,VslCharacterStructure *native,
    float gain,float shape,float elapsed);
void vsl_response_apply(VslResponseShape *s,VslEngine *e,VslObjectFrame *objects);
#endif

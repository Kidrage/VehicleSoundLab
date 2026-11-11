#ifndef VSL_RESPONSE_SHAPE_H
#define VSL_RESPONSE_SHAPE_H
#include "engine.h"
void vsl_response_init(VslResponseShape *s,double rate,double amount);
void vsl_response_clear(VslResponseShape *s);
void vsl_response_begin(VslResponseShape *s);
void vsl_response_pressure_strike(VslResponseShape *s,VslEngine *e,VslCharacterPressure *native,
    int bank,double gain,double shape,double elapsed);
void vsl_response_structure_strike(VslResponseShape *s,VslEngine *e,VslCharacterStructure *native,
    double gain,double shape,double elapsed);
void vsl_response_apply(VslResponseShape *s,VslEngine *e,VslObjectFrame *objects);
#endif

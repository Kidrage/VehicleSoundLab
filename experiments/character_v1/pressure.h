#ifndef VSL_CHARACTER_PRESSURE_H
#define VSL_CHARACTER_PRESSURE_H
#include "core/modal.h"
#include "profile.h"
typedef struct {
    VslMode mode[2][VSL_CHARACTER_PRESSURE_MODES];
    double history[2][128],rate;
    unsigned cursor;
} VslCharacterPressure;
void vsl_character_pressure_init(VslCharacterPressure *p,double rate);
void vsl_character_pressure_advance(VslCharacterPressure *p);
void vsl_character_pressure_strike(VslCharacterPressure *p,int bank,double gain,double shape,double elapsed);
void vsl_character_pressure_read(VslCharacterPressure *p,double right_delay,double output[2]);
#endif

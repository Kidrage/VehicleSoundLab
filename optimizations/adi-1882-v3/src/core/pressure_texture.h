#ifndef VSL_CHARACTER_PRESSURE_H
#define VSL_CHARACTER_PRESSURE_H
#include "core/modal.h"
#include "profiles/character.h"
typedef struct {
    VslMode mode[2][VSL_CHARACTER_PRESSURE_MODES];
    float history[2][128],rate;
    unsigned cursor;
} VslCharacterPressure;
void vsl_character_pressure_init(VslCharacterPressure *p,float rate);
void vsl_character_pressure_advance(VslCharacterPressure *p);
void vsl_character_pressure_strike(VslCharacterPressure *p,int bank,float gain,float shape,float elapsed);
void vsl_character_pressure_read(VslCharacterPressure *p,float right_delay,float output[2]);
#endif

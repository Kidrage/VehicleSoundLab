#ifndef VSL_CHARACTER_TYPES_H
#define VSL_CHARACTER_TYPES_H
#include "pressure_texture.h"
#include "structure_texture.h"
#include <stdint.h>
typedef struct {
    VslCharacterPressure pressure;
    VslCharacterStructure structure;
    double previous_phase,amount_pressure,amount_structure;
    double energy[10],shape[10],added[3],energy_min,energy_max;
    uint32_t seed[10];
    unsigned events[10];
    int eligible;
} VslCharacter;
#endif

#ifndef VSL_CHARACTER_EXPERIMENT_H
#define VSL_CHARACTER_EXPERIMENT_H
#include "core/engine.h"
#include "pressure.h"
#include "structure.h"
typedef struct {
    VslCharacterPressure pressure;
    VslCharacterStructure structure;
    double previous_phase,amount_pressure,amount_structure;
    double energy[10],shape[10],added[3],energy_min,energy_max;
    uint32_t seed[10];
    unsigned events[10];
    VslEngine *engine;
} VslCharacter;
void vsl_character_init(VslCharacter *s,VslEngine *engine,double pressure,double structure,uint32_t seed);
/* One bound offline engine at a time in this single-threaded host.
   Binding is deliberately outside V015 state, not a production audio API. */
void vsl_character_bind(VslCharacter *state);
void vsl_character_hook(VslEngine *engine,VslObjectFrame *objects);
void vsl_character_step(VslCharacter *state,VslEngine *engine,VslObjectFrame *objects);
unsigned vsl_character_events(const VslCharacter *state);
#endif

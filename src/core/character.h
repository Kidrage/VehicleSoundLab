#ifndef VSL_CHARACTER_H
#define VSL_CHARACTER_H
#include "engine.h"
void vsl_character_init(VslEngine *engine,uint32_t seed);
void vsl_character_tick(VslEngine *engine,VslObjectFrame *objects);
unsigned vsl_character_events(const VslCharacter *state);
#endif

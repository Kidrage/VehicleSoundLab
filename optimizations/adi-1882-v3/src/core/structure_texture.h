#ifndef VSL_CHARACTER_STRUCTURE_H
#define VSL_CHARACTER_STRUCTURE_H
#include "core/modal.h"
#include "profiles/character.h"
typedef struct { VslMode mode[VSL_CHARACTER_STRUCTURE_MODES]; } VslCharacterStructure;
void vsl_character_structure_init(VslCharacterStructure *p,float rate);
void vsl_character_structure_advance(VslCharacterStructure *p);
void vsl_character_structure_strike(VslCharacterStructure *p,float gain,float shape,float elapsed);
float vsl_character_structure_read(const VslCharacterStructure *p);
#endif

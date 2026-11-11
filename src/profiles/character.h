#ifndef VSL_CHARACTER_PROFILE_H
#define VSL_CHARACTER_PROFILE_H
#define VSL_CHARACTER_PRESSURE_MODES 3
#define VSL_CHARACTER_STRUCTURE_MODES 5
typedef struct { double hz,decay,weight; } VslCharacterMode;
typedef struct {
    VslCharacterMode pressure[VSL_CHARACTER_PRESSURE_MODES];
    VslCharacterMode structure[VSL_CHARACTER_STRUCTURE_MODES];
    double pressure_level,structure_level,mechanical_boost;
    double event_spread,shape_spread,event_memory;
} VslCharacterProfile;
const VslCharacterProfile *vsl_character_profile(void);
#endif

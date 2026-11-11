#ifndef VSL_MECHANICAL_PROFILE_H
#define VSL_MECHANICAL_PROFILE_H
#define VSL_MECHANICAL_MODES 5
typedef struct { double hz,decay,rotating_gain,fired_gain; } VslMechanicalMode;
typedef struct {
    VslMechanicalMode modes[VSL_MECHANICAL_MODES];
    double rotating_offset[2],level,cycle_spread;
} VslMechanicalProfile;
const VslMechanicalProfile *vsl_mechanical_profile(int profile);
#endif

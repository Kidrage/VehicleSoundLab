#include "fueling.h"
/* Shared engineering ECU/pressure settings, NOT measured Lamborghini maps.
   Fuel cut requires closed effective throttle and negative load, with RPM
   hysteresis. Neutral lift has a longer qualifying interval. */
static const VslFuelingProfile ice = {
    900,450, .015,.035, .14,.22,.06, .012,.009, .028,320,1.8
};
const VslFuelingProfile *vsl_fueling_profile(int profile) { (void)profile;return &ice; }

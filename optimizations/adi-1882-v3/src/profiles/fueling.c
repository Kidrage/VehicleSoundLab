#include "fueling.h"
/* Shared engineering ECU/pressure settings, NOT measured Lamborghini maps.
   Fuel cut requires closed effective throttle and negative load, with RPM
   hysteresis. Neutral lift has a longer qualifying interval. */
static const VslFuelingProfile ice = {
    900,450, .015f,.035f, .14f,.22f,.06f, .012f,.009f, .028f,320,1.8f
};
const VslFuelingProfile *vsl_fueling_profile(int profile) { (void)profile;return &ice; }

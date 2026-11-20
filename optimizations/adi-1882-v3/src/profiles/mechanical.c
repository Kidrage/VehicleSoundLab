#include "mechanical.h"
/* Shared engineering structural modes, NOT identified engine-block FRFs.
   360/540 crank degrees are idealised exhaust/intake closing surrogates,
   not measured Lamborghini cam timing. Vehicle fits can replace this table. */
static const VslMechanicalProfile ice = {
    {{610,.020f,.26f,.45f},{1180,.013f,.42f,.50f},{2240,.009f,.60f,.33f},
     {3870,.006f,.40f,.22f},{5820,.004f,.22f,.13f}},
    {360,540}, .10f,.10f
};
const VslMechanicalProfile *vsl_mechanical_profile(int profile) { (void)profile;return &ice; }

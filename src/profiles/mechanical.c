#include "mechanical.h"
/* Shared engineering structural modes, NOT identified engine-block FRFs.
   360/540 crank degrees are idealised exhaust/intake closing surrogates,
   not measured Lamborghini cam timing. Vehicle fits can replace this table. */
static const VslMechanicalProfile ice = {
    {{610,.020,.26,.45},{1180,.013,.42,.50},{2240,.009,.60,.33},
     {3870,.006,.40,.22},{5820,.004,.22,.13}},
    {360,540}, .10,.10
};
const VslMechanicalProfile *vsl_mechanical_profile(int profile) { (void)profile;return &ice; }

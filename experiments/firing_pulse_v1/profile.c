#include "profile.h"
/* An audition recipe, NOT measured cylinder pressure or a Lamborghini FRF.
   Keep the event source and its strength separate from legacy V011 voicing. */
static const FpProfile recipe={.000075,.000028,.35,.28,.60,1000,.28,.30};
const FpProfile *fp_profile(void) { return &recipe; }

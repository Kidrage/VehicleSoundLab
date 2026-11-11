#include "profiles/firing_source.h"
/* Frozen firing_pulse_v1 voicing plus live 18 ms transition time.
   Acoustic engineering recipe, not measured pressure, valve timing or FRF. */
static const VslPulseProfile recipe={.000075,.000028,.35,.28,.60,1000,.28,.30,.018};
const VslPulseProfile *vsl_pulse_profile(void) { return &recipe; }

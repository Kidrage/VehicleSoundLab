#include "profiles/firing_source.h"
/* Frozen firing_pulse_v1 voicing plus live 18 ms transition time.
   Acoustic engineering recipe, not measured pressure, valve timing or FRF. */
static const VslPulseProfile recipe={.000075f,.000028f,.35f,.28f,.60f,1000,.28f,.30f,.018f};
const VslPulseProfile *vsl_pulse_profile(void) { return &recipe; }

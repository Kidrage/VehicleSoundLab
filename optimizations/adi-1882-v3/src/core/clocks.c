#include "modules.h"
#include <math.h>
/* The 720-degree crank cycle drives combustion, NVH and mechanical modulation.
   Imported oscillator DNA has its own pitch law and cannot retime those layers. */
void vsl_clocks_tick(VslEngine *e) {
    float cycle_hz=e->control.rpm/120;
    e->control.phase=fmodf(e->control.phase+2*VSL_PI*cycle_hz/e->sample_rate,2*VSL_PI);
    e->detail.variation_phase=fmodf(e->detail.variation_phase+2*VSL_PI*cycle_hz*.74f/e->sample_rate,2*VSL_PI);
    if(e->dna.custom_count) {
        float pitch_hz=e->dna.custom_root*e->control.rpm/3000;
        e->dna.pitch_phase=fmodf(e->dna.pitch_phase+2*VSL_PI*pitch_hz/e->sample_rate,2*VSL_PI);
    }
}

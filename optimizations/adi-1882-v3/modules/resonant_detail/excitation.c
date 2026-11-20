#include "excitation.h"
#include "dsp/noise.h"
void rdt_excitation_init(RdtExcitation *p,uint64_t seed) { p->state=seed?seed:1;p->spare=0;p->has_spare=0; }
float rdt_excitation_next(RdtExcitation *p) {
    return vsl_normal(&p->state);
}

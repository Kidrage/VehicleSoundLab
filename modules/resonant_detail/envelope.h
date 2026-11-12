#ifndef VSL_RESONANT_DETAIL_ENVELOPE_H
#define VSL_RESONANT_DETAIL_ENVELOPE_H
#include "profile.h"
/* Supplied common source phase, in cycles. No internal engine clock. */
double rdt_envelope_amplitude(const RdtBand *band,double phase_cycles);
int rdt_envelope_valid(const RdtBand *band);
#endif

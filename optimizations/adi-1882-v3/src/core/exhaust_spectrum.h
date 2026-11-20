#ifndef VSL_EXHAUST_SPECTRUM_H
#define VSL_EXHAUST_SPECTRUM_H
#include "types.h"
/* Shared factory spectral shape. This is engineering voicing, not an
   identified manifold/microphone transfer or a source-time trajectory. */
float vsl_exhaust_envelope(const VslEngine *e,float cycle_order,float hz);
float vsl_exhaust_continuation(const VslEngine *e,int bank_order,int side);
#endif

#ifndef VSL_DENSE_OSCILLATOR_H
#define VSL_DENSE_OSCILLATOR_H
#include "model.h"
/* Offline diagnostic only. Caller supplies zeroable output, no source PCM. */
int do_render(const DoModel *model,double *mono);
#endif

#ifndef VSL_FIRING_SOURCE_H
#define VSL_FIRING_SOURCE_H
#include "engine.h"
int vsl_firing_source_init(VslFiringSource *s,double rate);
void vsl_firing_source_tick(VslFiringSource *s,const VslEngine *e,VslObjectFrame *o,const double main_pressure[2]);
#endif

#ifndef VSL_DNA_CHARACTER_DYNAMICS_H
#define VSL_DNA_CHARACTER_DYNAMICS_H
#include "core/engine.h"
/* 200 Hz voicing only. Independent retention of line/texture while coasting;
   no new generator, vehicle clock, master-gain change or measured-car claim. */
void dch_dynamics_targets(const VslEngine *engine,float *line,float *air);
#endif

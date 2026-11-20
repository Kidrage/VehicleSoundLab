#ifndef VSL_DNA_CHARACTER_MECHANICAL_H
#define VSL_DNA_CHARACTER_MECHANICAL_H
#include "core/types.h"
/* Same vehicle shaft/fueling clock. Only the retained mechanical feature is
   returned; old template signals never enter the DNA or output buses. */
void dch_mechanical_tick(VslEngine *engine,float follow,float mono[1]);
#endif

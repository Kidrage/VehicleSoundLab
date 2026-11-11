#ifndef VSL_DRIVE_AUX_MOTION_H
#define VSL_DRIVE_AUX_MOTION_H
#include "core/types.h"
/* Advances only the auxiliary crank/control adapter. The caller has already
   stepped the single driving controller and its voicing envelopes. */
void da_motion_tick(VslEngine *owner,double follow);
#endif

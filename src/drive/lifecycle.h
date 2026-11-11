#ifndef VSL_LIFECYCLE_H
#define VSL_LIFECYCLE_H
#include "core/types.h"
/* Returns one only when RUNNING; other states update rotation/permission here.
   Called once per simulation control tick, never from UI wall time. */
int vsl_lifecycle_step(VslDrive *d,const VslParams *p,double dt);
#endif

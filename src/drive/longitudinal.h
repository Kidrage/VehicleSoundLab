#ifndef VSL_LONGITUDINAL_H
#define VSL_LONGITUDINAL_H
#include "types.h"
void vsl_longitudinal_step(VslDrive *drive,double idle_rpm,double max_rpm,double dt);
#endif

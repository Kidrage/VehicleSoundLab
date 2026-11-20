#ifndef VSL_LONGITUDINAL_H
#define VSL_LONGITUDINAL_H
#include "types.h"
void vsl_longitudinal_step(VslDrive *drive,float idle_rpm,float max_rpm,float dt);
#endif

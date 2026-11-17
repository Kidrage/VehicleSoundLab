#ifndef VSL_DRIVE_H
#define VSL_DRIVE_H
#include "core/types.h"
#include "kinematic.h"
void vsl_drive_reset(VslDrive *d, int profile);
void vsl_drive_step(VslDrive *d, const VslParams *p, double dt);
void vsl_drive_step_kinematic(VslDrive *d,const VslParams *p,double dt,const VslKinematics *input);
const char *vsl_lifecycle_name(VslLifecycle state);
const char *vsl_operating_name(VslOperating state);
#endif

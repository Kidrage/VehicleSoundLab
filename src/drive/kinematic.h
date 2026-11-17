#ifndef VSL_DRIVE_KINEMATIC_H
#define VSL_DRIVE_KINEMATIC_H
#include "types.h"
/* External wheel kinematics; virtual engine RPM remains owned by one driver.
   This acoustic mapping is an engineering model, not a measured powertrain. */
typedef struct {double speed_mps,acceleration_mps2,tire_slip;} VslKinematics;
void vsl_kinematic_adopt(VslDrive *drive,const VslKinematics *input);
void vsl_kinematic_step(VslDrive *drive,const VslKinematics *input,double idle,double maxrpm,double dt);
#endif

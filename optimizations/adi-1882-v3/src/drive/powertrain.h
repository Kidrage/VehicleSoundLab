#ifndef VSL_POWERTRAIN_H
#define VSL_POWERTRAIN_H
#include "types.h"
float vsl_gear_ratio(int gear);
/* d(shaft angle)/d(road distance), rad/m, from the effective RPM/kph gearing. */
float vsl_angular_per_metre(int gear);
int vsl_transmitted_gear(const VslDrive *drive);
float vsl_available_torque(int profile,float rpm,float max_rpm);
float vsl_shaft_torque(int profile,float rpm,float idle,float max_rpm,float pedal);
float vsl_engine_loss(int profile,float rpm,float max_rpm);
float vsl_wheel_force(int profile,float torque_nm,float angular_per_metre,float clutch);
float vsl_engine_braking(const VslDrive *drive,float max_rpm);
#endif

#ifndef VSL_POWERTRAIN_H
#define VSL_POWERTRAIN_H
#include "types.h"
double vsl_gear_ratio(int gear);
/* d(shaft angle)/d(road distance), rad/m, from the effective RPM/kph gearing. */
double vsl_angular_per_metre(int gear);
int vsl_transmitted_gear(const VslDrive *drive);
double vsl_available_torque(int profile,double rpm,double max_rpm);
double vsl_shaft_torque(int profile,double rpm,double idle,double max_rpm,double pedal);
double vsl_engine_loss(int profile,double rpm,double max_rpm);
double vsl_wheel_force(int profile,double torque_nm,double angular_per_metre,double clutch);
double vsl_engine_braking(const VslDrive *drive,double max_rpm);
#endif

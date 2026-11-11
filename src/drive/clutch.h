#ifndef VSL_CLUTCH_H
#define VSL_CLUTCH_H
#include "types.h"
typedef struct {
    double torque_nm,requested_torque_nm,idle_torque_nm,governor_reduction_nm;
    double positive_capacity_nm,negative_capacity_nm,engine_pedal;
} VslClutchControl;
void vsl_clutch_control(VslDrive *drive,double idle_rpm,double max_rpm,
    double road_force_n,double service_force_n,double dt,VslClutchControl *control);
#endif

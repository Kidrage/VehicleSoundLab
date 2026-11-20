#ifndef VSL_CLUTCH_H
#define VSL_CLUTCH_H
#include "types.h"
typedef struct {
    float torque_nm,requested_torque_nm,idle_torque_nm,governor_reduction_nm;
    float positive_capacity_nm,negative_capacity_nm,engine_pedal;
} VslClutchControl;
void vsl_clutch_control(VslDrive *drive,float idle_rpm,float max_rpm,
    float road_force_n,float service_force_n,float dt,VslClutchControl *control);
#endif

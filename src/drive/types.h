#ifndef VSL_DRIVE_TYPES_H
#define VSL_DRIVE_TYPES_H
#include "fuel_types.h"
#include "vehicle_types.h"
typedef enum { VSL_OFF, VSL_READY, VSL_CRANK, VSL_CATCH, VSL_RUNNING, VSL_STOPPING } VslLifecycle;
typedef enum { VSL_IDLE, VSL_FREE_REV, VSL_PULL, VSL_CRUISE, VSL_OVERRUN, VSL_SHIFT_CUT, VSL_SHIFT_RECOVER, VSL_REV_MATCH, VSL_OPERATING_COUNT } VslOperating;
typedef enum { VSL_SHIFT_NONE, VSL_SHIFT_DISCONNECT, VSL_SHIFT_MATCH, VSL_SHIFT_ENGAGE } VslShiftStage;
typedef enum { VSL_BENCH, VSL_PEDALS, VSL_AUTODRIVE } VslDriveMode;
typedef struct {
    VslLifecycle lifecycle;
    VslOperating operating;
    int profile, gear, previous_gear, last_start, requested_gear, shifting;
    double rpm, speed_kph, throttle, brake, load, acceleration;
    double life_seconds, running_seconds, shift_seconds, shift_from_rpm, shift_lock;
    double combustion, shift_gain, throttle_rate, rpm_rate, previous_rpm;
    double life_entry_rpm, life_entry_rate, lifecycle_flare;
    VslShiftStage shift_stage;
    int shift_direction;
    double stage_seconds, clutch_transfer, blip, engine_throttle, engine_throttle_rate;
    double shift_target_rpm, shift_error;
    unsigned aborted_shifts;
    double armed_seconds, peak_throttle, release_seconds, cooldown;
    int overrun_armed;
    unsigned start_events, shift_events, overrun_events;
    double overrun_strength;
    VslFuel fuel;
    VslVehicle vehicle;
    double clutch_capacity_nm,shift_target_rate;
    VslCouplingAudit coupling_audit;
} VslDrive;
#endif

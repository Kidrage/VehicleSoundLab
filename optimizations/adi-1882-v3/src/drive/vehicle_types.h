#ifndef VSL_VEHICLE_TYPES_H
#define VSL_VEHICLE_TYPES_H
/* Last integration sample. Forces precede integration; acceleration includes
   the forward-only rest stop. Not independent engine/wheel telemetry. */
typedef struct {
    int transmitted_gear;
    float sample_speed_mps, sample_rpm, sample_pedal, sample_clutch;
    float available_torque_nm, shaft_torque_nm;
    float wheel_force_n, rolling_n, aerodynamic_n, service_brake_n;
    float engine_brake_n, effective_mass_kg, acceleration_mps2;
    float requested_torque_nm,idle_torque_nm,governor_reduction_nm;
    float clutch_capacity_nm,clutch_torque_nm,clutch_slip_rad_s;
    float engine_work_j,road_work_j,clutch_heat_j,transmission_loss_j,numerical_loss_j;
    float energy_before_j,energy_after_j,energy_error_j;
    int clutch_locked,solver_active;
} VslVehicle;
/* Accumulate every RUNNING integration step, not sparse CSV observations.
   Lifecycle kinematics and bench operation are explicitly outside this sum. */
typedef struct {
    unsigned steps;
    float kinetic_delta_j,engine_work_j,road_work_j,clutch_heat_j;
    float transmission_loss_j,numerical_loss_j,max_energy_error_j;
} VslCouplingAudit;
#endif

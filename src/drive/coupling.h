#ifndef VSL_COUPLING_H
#define VSL_COUPLING_H
/* Passive, forward-only two-inertia coupling. Constant inputs per step;
   backwards Euler, with exact unilateral rest constraints and bounded
   Coulomb clutch friction. Gear k is rad/m, not dimensionless. */
typedef struct {
    double omega_rad_s,speed_mps,engine_torque_nm,road_force_n;
    double engine_inertia_kg_m2,mass_kg,angular_per_metre,efficiency;
    double positive_capacity_nm,negative_capacity_nm,dt;
} VslCouplingInput;
typedef struct {
    double omega_rad_s,speed_mps,clutch_torque_nm,slip_rad_s;
    double engine_work_j,road_work_j,clutch_heat_j,transmission_loss_j;
    double numerical_loss_j,energy_before_j,energy_after_j,energy_error_j;
    int locked;
} VslCouplingResult;
int vsl_coupling_solve(const VslCouplingInput *input,VslCouplingResult *result);
#endif

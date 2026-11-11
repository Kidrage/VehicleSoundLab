#ifndef VSL_VEHICLE_PROFILE_H
#define VSL_VEHICLE_PROFILE_H
/* SI longitudinal proxy. Only the V10 peak torque/power anchors are sourced;
   running mass, losses, grip and inertias are engineering values. */
typedef struct {
    double mass_kg, wheel_equivalent_kg, engine_inertia_kg_m2;
    double air_density_kg_m3, drag_area_m2, rolling_coefficient;
    double efficiency, traction_mu, brake_g, brake_exponent;
    double peak_torque_nm, loss_low_nm, loss_high_nm;
    double limiter_start;
    double gear_rpm_per_kph[7];
} VslVehicleProfile;
const VslVehicleProfile *vsl_vehicle_profile(int profile);
double vsl_torque_fraction(double normalized_rpm);
#endif

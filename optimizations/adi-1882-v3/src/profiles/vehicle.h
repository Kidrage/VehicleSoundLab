#ifndef VSL_VEHICLE_PROFILE_H
#define VSL_VEHICLE_PROFILE_H
/* SI longitudinal proxy. Only the V10 peak torque/power anchors are sourced;
   running mass, losses, grip and inertias are engineering values. */
typedef struct {
    float mass_kg, wheel_equivalent_kg, engine_inertia_kg_m2;
    float air_density_kg_m3, drag_area_m2, rolling_coefficient;
    float efficiency, traction_mu, brake_g, brake_exponent;
    float peak_torque_nm, loss_low_nm, loss_high_nm;
    float limiter_start;
    float gear_rpm_per_kph[7];
} VslVehicleProfile;
const VslVehicleProfile *vsl_vehicle_profile(int profile);
float vsl_torque_fraction(float normalized_rpm);
#endif

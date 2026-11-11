#ifndef VSL_CLUTCH_PROFILE_H
#define VSL_CLUTCH_PROFILE_H
/* Engineering automatic-clutch/idle/traction controls, not ECU calibration. */
typedef struct {
    double capacity_nm,capacity_tau,launch_rpm,launch_gain_nm_per_rad_s;
    double governor_per_s,idle_gain_nm_per_rpm,idle_max_nm,idle_window_rpm;
    double match_undershoot_rpm,upshift_sync_capacity_nm;
} VslClutchProfile;
const VslClutchProfile *vsl_clutch_profile(int profile);
#endif

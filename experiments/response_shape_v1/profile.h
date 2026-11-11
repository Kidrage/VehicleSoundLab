#ifndef VSL_RESPONSE_PROFILE_H
#define VSL_RESPONSE_PROFILE_H
typedef struct {
    double decay_scale[3];
    double load_weight,rpm_weight,event_weight;
    double rpm_low,rpm_high;
} VslResponseProfile;
const VslResponseProfile *vsl_response_profile(void);
double vsl_response_coordinate(double rpm,double pull,double event_shape,double amount);
#endif

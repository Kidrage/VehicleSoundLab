#ifndef VSL_RESPONSE_PROFILE_H
#define VSL_RESPONSE_PROFILE_H
typedef struct {
    float decay_scale[3];
    float load_weight,rpm_weight,event_weight;
    float rpm_low,rpm_high;
} VslResponseProfile;
const VslResponseProfile *vsl_response_profile(void);
float vsl_response_coordinate(float rpm,float pull,float event_shape,float amount);
#endif

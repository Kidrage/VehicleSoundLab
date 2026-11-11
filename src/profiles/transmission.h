#ifndef VSL_TRANSMISSION_PROFILE_H
#define VSL_TRANSMISSION_PROFILE_H
/* Engineering actuator timing. Not measured Lamborghini transmission data. */
typedef struct {
    double disconnect, up_match_min, down_match_min, engage, timeout, cooldown;
    double match_response, max_rise, max_fall, tolerance, engage_tolerance;
    double cut_floor, blip_max;
} VslTransmissionProfile;
const VslTransmissionProfile *vsl_transmission_profile(int profile);
#endif

#ifndef VSL_EVENT_COLOR_PROFILE_H
#define VSL_EVENT_COLOR_PROFILE_H
typedef struct {
    double split_hz[2],follow_seconds,mid_depth,high_depth,irregularity_reference;
} VslEventColorProfile;
const VslEventColorProfile *vsl_event_color_profile(void);
#endif

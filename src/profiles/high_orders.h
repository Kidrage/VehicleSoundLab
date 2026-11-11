#ifndef VSL_HIGH_ORDER_PROFILE_H
#define VSL_HIGH_ORDER_PROFILE_H
/* Engineering high-order spectrum, kept apart from the oscillator runtime. */
typedef struct {
    double center_hz, log_width, level, density_reference_hz, upper_hz;
    double continuation_end_order, reference_detail;
} VslHighOrderProfile;
const VslHighOrderProfile *vsl_high_order_profile(int profile);
#endif

#ifndef VSL_STEREO_RESONANCE_PROFILE_H
#define VSL_STEREO_RESONANCE_PROFILE_H
#include "resonant_detail/profile.h"
#define RVS_MAX_ORDER 24
#define RVS_MAX_DIM (2*RVS_MAX_ORDER)
#define RVS_MAX_BANDS 12
typedef struct {
    unsigned order;
    double low_hz,high_hz,gain;
    double a[RVS_MAX_ORDER][2][2],noise[2][2];
    /* Positive Lyapunov certificate for the companion state, checked non-RT. */
    double certificate[RVS_MAX_DIM][RVS_MAX_DIM];
    RdtBand post;
} RvsBand;
typedef struct {
    unsigned rate,count,warmup_frames;
    double base_hz;
    RvsBand band[RVS_MAX_BANDS];
} RvsProfile;
int rvs_profile_valid(const RvsProfile *profile);
#endif

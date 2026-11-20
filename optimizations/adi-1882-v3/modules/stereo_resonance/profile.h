#ifndef VSL_STEREO_RESONANCE_PROFILE_H
#define VSL_STEREO_RESONANCE_PROFILE_H
#include "dsp_support/config.h"
#include "resonant_detail/profile.h"
#ifndef RVS_MAX_ORDER
#define RVS_MAX_ORDER 24
#endif
#define RVS_MAX_DIM (2*RVS_MAX_ORDER)
#ifndef RVS_MAX_BANDS
#define RVS_MAX_BANDS 12
#endif
typedef struct {
    unsigned order;
    float low_hz,high_hz,gain;
    float a[RVS_MAX_ORDER][2][2],noise[2][2];
    /* Positive Lyapunov certificate for the companion state, checked non-RT. */
    float certificate[RVS_MAX_DIM][RVS_MAX_DIM];
    RdtBand post;
} RvsBand;
typedef struct {
    unsigned rate,count,warmup_frames;
    float base_hz;
    RvsBand band[RVS_MAX_BANDS];
} RvsProfile;
int rvs_profile_valid(const RvsProfile *profile);
#endif

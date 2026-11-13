#ifndef VSL_SPECTRAL_TEXTURE_PROFILE_H
#define VSL_SPECTRAL_TEXTURE_PROFILE_H
#include "partitioned_fir/filter.h"
#define SF_MAX_BANDS 12
typedef struct {unsigned count;double gain,right_over_left,taps[PF_MAX_TAPS];} SfBand;
typedef struct {unsigned rate,count,warmup_frames;SfBand band[SF_MAX_BANDS];} SfProfile;
int sf_profile_valid(const SfProfile *profile);
#endif

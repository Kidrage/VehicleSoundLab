#ifndef VSL_SPECTRAL_TEXTURE_PROFILE_H
#define VSL_SPECTRAL_TEXTURE_PROFILE_H
#include "dsp_support/config.h"
#include "partitioned_fir/filter.h"
#ifndef SF_MAX_BANDS
#define SF_MAX_BANDS 12
#endif
typedef struct {unsigned count;float gain,right_over_left,taps[PF_MAX_TAPS];unsigned decimation;} SfBand;
typedef struct {unsigned rate,count,warmup_frames;SfBand band[SF_MAX_BANDS];} SfProfile;
int sf_profile_valid(const SfProfile *profile);
#endif

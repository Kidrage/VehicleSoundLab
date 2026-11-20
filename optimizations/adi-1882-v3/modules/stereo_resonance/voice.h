#ifndef VSL_STEREO_RESONANCE_VOICE_H
#define VSL_STEREO_RESONANCE_VOICE_H
#include "profile.h"
#include "resonant_detail/excitation.h"
#include "resonant_detail/filter.h"
typedef struct {
    const RvsProfile *profile;
    RdtExcitation excitation[RVS_MAX_BANDS][2];
    float history[RVS_MAX_BANDS][RVS_MAX_ORDER][2];
    RdtFilter post[RVS_MAX_BANDS][2];
    unsigned at[RVS_MAX_BANDS];
    float amount,target,follow;
    uint64_t frame;
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
    /* Borrowed block cache, consumed by the same serialized audio call. */
    const float *prepared;
    unsigned prepared_frames;
#endif
} RvsVoice;
/* Validation and warmup are non-RT. Borrowed immutable profile outlives voice. */
int rvs_voice_init(RvsVoice *voice,const RvsProfile *profile,uint64_t seed,float amount);
int rvs_voice_set(RvsVoice *voice,float amount);
/* New continuous excitation, no oscillator cloud/PCM/private RPM or phase clock. */
int rvs_voice_tick(RvsVoice *voice,float output[2],float raw[2]);
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
/* Only the independent excitation/filter chain is rendered ahead. Amount and
   public frame advance when each prepared sample is consumed. */
int rvs_voice_prepare(RvsVoice *voice,float *stereo,unsigned frames);
#endif
#endif

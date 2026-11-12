#ifndef VSL_STEREO_RESONANCE_VOICE_H
#define VSL_STEREO_RESONANCE_VOICE_H
#include "profile.h"
#include "resonant_detail/excitation.h"
#include "resonant_detail/filter.h"
typedef struct {
    const RvsProfile *profile;
    RdtExcitation excitation[RVS_MAX_BANDS][2];
    double history[RVS_MAX_BANDS][RVS_MAX_ORDER][2];
    RdtFilter post[RVS_MAX_BANDS][2];
    unsigned at[RVS_MAX_BANDS];
    double amount,target,follow;
    uint64_t frame;
} RvsVoice;
/* Validation and warmup are non-RT. Borrowed immutable profile outlives voice. */
int rvs_voice_init(RvsVoice *voice,const RvsProfile *profile,uint64_t seed,double amount);
int rvs_voice_set(RvsVoice *voice,double amount);
/* New continuous excitation, no oscillator cloud/PCM/private RPM or phase clock. */
int rvs_voice_tick(RvsVoice *voice,double output[2],double raw[2]);
#endif

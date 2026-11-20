#ifndef VSL_RESIDUAL_ATLAS_VOICE_H
#define VSL_RESIDUAL_ATLAS_VOICE_H
#include "bank.h"
#include "sound_residual/oscillator.h"
typedef struct {
    const RaBank *bank; /* Immutable and alive until voice destruction. */
    SrCloud cloud;
    float root,root_target,gain,gain_target,follow,blend;
    float covariance[SR_MAX_BANDS][4]; /* P_L,P_R,Re(conj(L)*R),Im. */
    unsigned lower,upper;int coverage;uint64_t frame;
} RaVoice;
int ra_voice_init(RaVoice *voice,const RaBank *bank,uint64_t seed,float root,float gain);
int ra_voice_set(RaVoice *voice,float root,float gain);
/* No allocation/I/O. raw excludes smoothed gain; output includes it. Zero
   amount still advances all carrier phases and spectral followers. */
void ra_voice_tick(RaVoice *voice,float output[2],float raw[2]);
#endif

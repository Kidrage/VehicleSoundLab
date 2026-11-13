#ifndef VSL_SPECTRAL_MOTION_VOICE_H
#define VSL_SPECTRAL_MOTION_VOICE_H
#include "profile.h"
#include <stdint.h>
typedef struct SpmVoice SpmVoice;
/* Non-RT allocation/compile/prewarm. The spectral bank, map and channel
   ratios are copied. Only immutable profile->motion must outlive the voice.
   No source timeline or room model. */
SpmVoice *spm_voice_create(const SpmProfile *profile,uint64_t seed,double amount);
void spm_voice_destroy(SpmVoice *voice);
/* RT amount0..1, finite18ms ramp; no restart when target unchanged. */
int spm_voice_set(SpmVoice *voice,double amount);
/* RT: all bands and amplitude RNG advance at zero. Controls are applied at
   output sample time, after the FIR's internal excitation prefetch.
   Amount==0 uses original spectral sum arithmetic exactly. Optional bands
   receives spectral->count post-motion left contributions. Buffers must not
   overlap each other or voice/profile. Invalid calls do not advance. */
int spm_voice_tick(SpmVoice *voice,double stereo[2],double *bands);
#endif

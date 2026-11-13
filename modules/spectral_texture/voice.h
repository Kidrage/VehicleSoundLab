#ifndef VSL_SPECTRAL_TEXTURE_VOICE_H
#define VSL_SPECTRAL_TEXTURE_VOICE_H
#include "profile.h"
#include <stdint.h>
typedef struct SfBank SfBank;
typedef struct SfVoice SfVoice;
/* Non-RT create/destroy only. Bank owns compiled coefficients/scalars; the
   input profile may then be destroyed. Bank must outlive all its voices. */
SfBank *sf_bank_create(const SfProfile *profile);
void sf_bank_destroy(SfBank *bank);
SfVoice *sf_voice_create(const SfBank *bank,uint64_t seed);
void sf_voice_destroy(SfVoice *voice);
/* RT fresh excitation and immutable spectral filters, no room or envelope.
   Internal excitation is generated ahead in256sample blocks; controls/gates
   belong after output, at the actual sample clock. Not an external-input IR.
   Every call advances all bands. Outputs must not overlap voice or bank. */
int sf_voice_tick(SfVoice *voice,double stereo[2],double bands[SF_MAX_BANDS]);
int sf_voice_process(SfVoice *voice,double *interleaved,unsigned frames);
#endif

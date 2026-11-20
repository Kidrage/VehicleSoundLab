#ifndef VSL_HARMONIC_BODY_MIX_H
#define VSL_HARMONIC_BODY_MIX_H
#include <stdint.h>
typedef struct {
    float amount, target, envelope, follow, scale;
    uint64_t frame;
} HbMix;
/* Move LF from DNA's gain envelope to a separate body envelope. Unity shared
   envelopes/scale reconstruct the old full source for every amount. No RNG,
   filter delay, oscillator, I/O or allocation; the caller supplies one tap. */
int hb_mix_init(HbMix *mix,unsigned rate,float amount,float scale);
int hb_mix_set(HbMix *mix,float amount);
void hb_mix_tick(HbMix *mix,const float full[2],const float low[2],
    float dna_envelope,float body_envelope,float dna[2],float body[2]);
#endif

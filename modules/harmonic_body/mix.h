#ifndef VSL_HARMONIC_BODY_MIX_H
#define VSL_HARMONIC_BODY_MIX_H
#include <stdint.h>
typedef struct {
    double amount, target, envelope, follow, scale;
    uint64_t frame;
} HbMix;
/* Move LF from DNA's gain envelope to a separate body envelope. Unity shared
   envelopes/scale reconstruct the old full source for every amount. No RNG,
   filter delay, oscillator, I/O or allocation; the caller supplies one tap. */
int hb_mix_init(HbMix *mix,unsigned rate,double amount,double scale);
int hb_mix_set(HbMix *mix,double amount);
void hb_mix_tick(HbMix *mix,const double full[2],const double low[2],
    double dna_envelope,double body_envelope,double dna[2],double body[2]);
#endif

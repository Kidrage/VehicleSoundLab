#ifndef VSL_DNA_ATLAS_VOICE_H
#define VSL_DNA_ATLAS_VOICE_H
#include "bank.h"
#include "texture.h"
#include "harmonic_body/band.h"

typedef struct {
    const SaBank *bank;
    SdTexture texture[SA_MAX_ANCHORS];
    double phase, root_hz, root_target, detail, detail_target, gain, gain_target, follow;
    unsigned lower, upper;
    double blend;
    int coverage; /* -1 below / 0 within / +1 above observed root interval. */
    uint64_t frame;
} SaVoice;

/* One harmonic clock across the atlas. Each anchor has independent RNG/state,
   initialized with the explicit seed; all advance, including muted anchors.
   root 0..1000Hz (0 pauses the clock), detail/gain 0..1. No file I/O/allocation. */
int sa_voice_init(SaVoice *voice, const SaBank *bank, uint64_t seed, double root_hz, double detail, double gain);
int sa_voice_set(SaVoice *voice, double root_hz, double detail, double gain);
void sa_voice_tick(SaVoice *voice, double stereo[2]);
/* Optional LF sum from the same per-harmonic samples/phase. Full output and
   voice state equal sa_voice_tick; invalid band rejects without advancing. */
int sa_voice_tick_body(SaVoice *voice,const HbBand *band,double stereo[2],double body[2]);
void sa_voice_process(SaVoice *voice, double *stereo, unsigned frames);
#endif

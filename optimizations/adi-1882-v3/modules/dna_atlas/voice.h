#ifndef VSL_DNA_ATLAS_VOICE_H
#define VSL_DNA_ATLAS_VOICE_H
#include "bank.h"
#include "dsp/dna_table.h"
#include "texture.h"
#include "harmonic_body/band.h"
/* Cache the first two anchors; any additional anchors keep the original
   storage path. This limits L1 use without reducing the bank's eight anchors. */
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_FIR_TAPS) && VSL_DSP_FIR_TAPS <= 512
/* This build spends L1 on the current one-anchor V10 and its RDT filters.
   Further anchors retain their original state and use the uncached path. */
#define SA_CACHE_ANCHORS 1
#else
#define SA_CACHE_ANCHORS 2
#endif
typedef struct {
    unsigned count;
    uint64_t updates[SA_CACHE_ANCHORS];
    float mean[SA_CACHE_ANCHORS][SD_MAX_HARMONICS][4];
    float unit[SA_CACHE_ANCHORS][SD_MAX_HARMONICS][4];
    float left[SA_CACHE_ANCHORS][SD_MAX_HARMONICS][4];
    float right[SA_CACHE_ANCHORS][SD_MAX_HARMONICS][4];
} SaSampleCache;

typedef struct {
    const SaBank *bank;
    SdTexture texture[SA_MAX_ANCHORS];
    float phase, root_hz, root_target, detail, detail_target, gain, gain_target, follow;
    unsigned lower, upper;
    float blend;
    int coverage; /* -1 below / 0 within / +1 above observed root interval. */
    uint64_t frame;
    SaSampleCache *sample_cache;
    SaTable *table;
} SaVoice;

/* One harmonic clock across the atlas. Each anchor has independent RNG/state,
   initialized with the explicit seed; all advance, including muted anchors.
   root 0..1000Hz (0 pauses the clock), detail 0..1.3, gain 0..1. No file I/O/allocation. */
int sa_voice_init(SaVoice *voice, const SaBank *bank, uint64_t seed, float root_hz, float detail, float gain);
/* Optional caller-owned hot data, e.g. in L1. Only byte copies are cached;
   texture state and random streams remain in the voice. Attach outside
   processing; an exclusive cache and immutable bank must outlive the voice. */
void sa_voice_sample_cache(SaVoice *voice,SaSampleCache *cache);
int sa_voice_set(SaVoice *voice, float root_hz, float detail, float gain);
void sa_voice_tick(SaVoice *voice, float stereo[2]);
/* Optional LF sum from the same per-harmonic samples/phase. Full output and
   voice state equal sa_voice_tick; invalid band rejects without advancing. */
int sa_voice_tick_body(SaVoice *voice,const HbBand *band,float stereo[2],float body[2]);
/* Optional common L/R harmonic magnitude shape, applied before full/LF sums.
   Borrowed gain array has bank->harmonics finite positive entries <=16,
   compiled/validated outside audio. Amount0 and NULL gain are exact bypass.
   Caller owns amount smoothing; no new oscillator, random draw or phase. */
int sa_voice_tick_shaped_body(SaVoice *voice,const HbBand *band,const float *gain,float amount,float stereo[2],float body[2]);
/* Same shaped full signal when the caller does not request the LF tap. */
int sa_voice_tick_shaped(SaVoice *voice,const float *gain,float amount,float stereo[2]);
void sa_voice_process(SaVoice *voice, float *stereo, unsigned frames);
#endif

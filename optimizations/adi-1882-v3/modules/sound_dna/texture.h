#ifndef VSL_SOUND_DNA_TEXTURE_H
#define VSL_SOUND_DNA_TEXTURE_H
#include "profile.h"
#include <stdint.h>
typedef struct {
    uint64_t rng,updates;float spare;int has_spare;
    float pc[SD_MAX_COMPONENTS],residual[SD_MAX_HARMONICS][4];
    float left[SD_MAX_HARMONICS][4],right[SD_MAX_HARMONICS][4];
    float fraction;
    /* Derived from the immutable profile at initialization, with the same
       FP32 expressions used by the original per-update computation. */
    float common_scale[SD_MAX_COMPONENTS],pc_innovation[SD_MAX_COMPONENTS];
    float residual_scale[SD_MAX_HARMONICS],residual_innovation[SD_MAX_HARMONICS];
} SdTexture;
void sd_texture_init(SdTexture *texture,const SdProfile *profile,uint64_t seed);
void sd_texture_prepare(SdTexture *texture,const SdProfile *profile);
/* Optional batching for already-aligned texture streams. Reuses identical
   Gaussian innovations, preserving every anchor's RNG/state and arithmetic.
   Different dimensions/fractions/RNG states fall back to serial preparation.
   Valid initialized profiles/textures required; count0 is a no-op. */
void sd_texture_prepare_batch(SdTexture *textures,const SdProfile *const *profiles,unsigned count);
#endif

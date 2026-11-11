#ifndef VSL_SOUND_DNA_TEXTURE_H
#define VSL_SOUND_DNA_TEXTURE_H
#include "profile.h"
#include <stdint.h>
typedef struct {
    uint64_t rng,updates;double spare;int has_spare;
    double pc[SD_MAX_COMPONENTS],residual[SD_MAX_HARMONICS][4];
    double left[SD_MAX_HARMONICS][4],right[SD_MAX_HARMONICS][4];
    double fraction;
} SdTexture;
void sd_texture_init(SdTexture *texture,const SdProfile *profile,uint64_t seed);
void sd_texture_prepare(SdTexture *texture,const SdProfile *profile);
#endif

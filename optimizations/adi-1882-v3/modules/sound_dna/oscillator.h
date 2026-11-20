#ifndef VSL_SOUND_DNA_OSCILLATOR_H
#define VSL_SOUND_DNA_OSCILLATOR_H
#include "texture.h"
typedef struct {float phase,unit[SD_MAX_HARMONICS][4];} SdOscillator;
void sd_oscillator_init(SdOscillator *oscillator,const SdProfile *profile);
void sd_oscillator_sample(SdOscillator *oscillator,const SdTexture *texture,const SdProfile *profile,float amount,float output[2]);
#endif

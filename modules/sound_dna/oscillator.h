#ifndef VSL_SOUND_DNA_OSCILLATOR_H
#define VSL_SOUND_DNA_OSCILLATOR_H
#include "texture.h"
typedef struct {double phase,unit[SD_MAX_HARMONICS][4];} SdOscillator;
void sd_oscillator_init(SdOscillator *oscillator,const SdProfile *profile);
void sd_oscillator_sample(SdOscillator *oscillator,const SdTexture *texture,const SdProfile *profile,double amount,double output[2]);
#endif

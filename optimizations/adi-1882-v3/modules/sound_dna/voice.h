#ifndef VSL_SOUND_DNA_VOICE_H
#define VSL_SOUND_DNA_VOICE_H
#include "oscillator.h"
typedef struct {
    const SdProfile *model;SdTexture texture;SdOscillator oscillator;
    uint64_t frame;
    float pitch,pitch_target,amount,amount_target,gain,gain_target,follow;
} SdVoice;
int sd_voice_init(SdVoice *voice,const SdProfile *profile,uint64_t seed,float relative_pitch,float texture_amount,float gain);
int sd_voice_set(SdVoice *voice,float relative_pitch,float texture_amount,float gain);
/* DNA output only: two observation channels, no engine/driving state, PAD,
   noise, room, loudness matching, device I/O, allocations or source playback. */
void sd_voice_process(SdVoice *voice,float *stereo,unsigned frames);
#endif

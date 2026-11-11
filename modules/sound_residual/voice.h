#ifndef VSL_SOUND_RESIDUAL_VOICE_H
#define VSL_SOUND_RESIDUAL_VOICE_H
#include "oscillator.h"
typedef struct {
    SrCloud cloud;uint64_t frame;int initialized;
    double pitch,pitch_target,gain,gain_target,follow;
} SrVoice;
/* Init copies all runtime parameters; profile storage may then be released. */
int sr_voice_init(SrVoice *voice,const SrProfile *profile,uint64_t seed,double pitch,double gain);
int sr_voice_set(SrVoice *voice,double pitch,double gain);
/* Interleaved stereo double; no allocation, I/O, or drive/spatial state. */
int sr_voice_process(SrVoice *voice,double *output,unsigned frames);
#endif

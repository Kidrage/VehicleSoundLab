#ifndef VSL_RESIDUAL_DENSE_VOICE_H
#define VSL_RESIDUAL_DENSE_VOICE_H
#include "carrier.h"
typedef struct {
    RdCloud cloud;uint64_t frame;int initialized;
    double pitch,pitch_target,gain,gain_target,follow;
} RdVoice;
/* Caller owns/preallocates the large state outside the audio callback.
   Init copies all moments; profile/count storage may then be released. */
int rd_voice_init(RdVoice *voice,const SrProfile *profile,const unsigned counts[SR_MAX_BANDS],uint64_t seed,double pitch,double gain);
int rd_voice_set(RdVoice *voice,double pitch,double gain);
/* 48kHz double stereo, no allocation/I/O/UI/driver/spatial work. */
int rd_voice_process(RdVoice *voice,double *stereo,unsigned frames);
#endif

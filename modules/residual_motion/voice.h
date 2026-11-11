#ifndef VSL_RESIDUAL_MOTION_VOICE_H
#define VSL_RESIDUAL_MOTION_VOICE_H
#include "envelope.h"
#include "sound_residual/voice.h"
typedef struct {
    SrVoice source;
    RmEnvelope motion;
    unsigned partials;
} RmVoice;
int rm_voice_init(RmVoice *voice,const SrProfile *source,const RmProfile *motion,
                   uint64_t source_seed,uint64_t motion_seed,double pitch,double gain,double amount);
int rm_voice_set(RmVoice *voice,double pitch,double gain,double amount);
/* raw/output interleaved stereo double. raw may beNULL; buffers must not alias.
   No allocations/I/O. Amount0 reproduces the existing SrVoice samples. */
int rm_voice_process(RmVoice *voice,double *output,double *raw,unsigned frames);
#endif

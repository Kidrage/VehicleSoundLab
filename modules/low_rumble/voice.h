#ifndef VSL_LOW_RUMBLE_VOICE_H
#define VSL_LOW_RUMBLE_VOICE_H
#include "cloud.h"
typedef struct {double b0,b1,b2,a1,a2,z1,z2;} LrFilter;
typedef struct {
    const LrProfile *profile;
    LrCloud cloud;
    LrFilter highpass,lowpass;
    double pitch,pitch_target,amount,amount_target,follow;
} LrVoice;
/* Profile is borrowed/immutable for the running voice's lifetime. */
int lr_voice_init(LrVoice *voice,const LrProfile *profile,uint64_t seed,double pitch,double amount);
int lr_voice_set(LrVoice *voice,double pitch,double amount);
/* ONE mono source. No allocation, file I/O, source PCM, room or LFE routing. */
void lr_voice_process(LrVoice *voice,double *mono,unsigned frames);
#endif

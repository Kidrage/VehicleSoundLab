#ifndef VSL_START_TEXTURE_VOICE_H
#define VSL_START_TEXTURE_VOICE_H
#include "profile.h"
#include "sound_residual/oscillator.h"
typedef struct {
    SrCloud cloud;
    float envelope, amount, amount_target, attack, release, follow;
    uint64_t frame;
    int gate, initialized;
    StProfile profile;
    float position,position_target,coefficient[SR_MAX_BANDS][4];
} StVoice;
/* Spectrum copied into cloud at init. Profile need not outlive the voice.
   Caller provides storage. No I/O, allocation, controller or spatial render here. */
int st_voice_init(StVoice *voice,const StProfile *profile,uint64_t seed,float amount);
/* Gate is exactly0/1, normally the unique driver's CRANK permission.
   Repeated calls and new starts never reset oscillator phases. */
int st_voice_set(StVoice *voice,int gate,float amount);
/* Unitless spectral progress, NOT oscillator pitch or physical RPM. */
int st_voice_position(StVoice *voice,float position);
/* Optional raw is before gate/amount; both captures are observed L/R.
   Continuous source generation even while closed preserves chunk/amount identity. */
int st_voice_process(StVoice *voice,float *stereo,float *raw,unsigned frames);
#endif

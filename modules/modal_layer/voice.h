#ifndef VSL_MODAL_LAYER_VOICE_H
#define VSL_MODAL_LAYER_VOICE_H
#include "profile.h"
#include "modal_source/voice.h"
#include "resonant_detail/voice.h"
typedef struct {
    const MlProfile *profile;
    MsVoice modal;
    RdtVoice detail;
    double position,step;
    unsigned remaining;
    int gate;
    uint64_t frame;
} MlVoice;
typedef struct {
    double modal[2],detail[2],raw[2],output[2];
    double weight,keep;
} MlFrame;
/* Non-RT, validate then prewarm resonators. Immutable profile storage remains
   caller-owned. Modal starts at its initial phase after filter prewarming. */
int ml_voice_init(MlVoice *voice,const MlProfile *profile,uint64_t seed);
/* RT, both generators advance even with gate0/envelope0. Repeated gate does
   not restart a finite ramp. Cubic weight and complementary linear mixing;
   re-targeting preserves position, with no equal-power loudness compensation.
   Caller-supplied envelope is0..8; profile level_gain is a separate fixed trim
   after raw timbre generation. No inferred RPM or shared engine phase. */
int ml_voice_tick(MlVoice *voice,int gate,double envelope,MlFrame *frame);
#endif

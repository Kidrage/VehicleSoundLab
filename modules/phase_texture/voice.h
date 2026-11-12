#ifndef VSL_PHASE_TEXTURE_VOICE_H
#define VSL_PHASE_TEXTURE_VOICE_H
#include "motion.h"
#include "sound_dna/voice.h"
typedef struct {
    PtMotion motion;
    const SdProfile *model;
    double amount,target,follow,mask[SD_MAX_HARMONICS];
} PtVoice;
/* A source adapter, no controller, PCM, allocation, I/O or spatial rendering.
   0..1 spans bypass..accepted LIGHT design scale only, not the medium trial.
   The supplied initialized SdVoice keeps its own clock/amplitude RNG. */
int pt_voice_init(PtVoice *voice,const SdProfile *profile,uint64_t seed,double amount);
int pt_voice_set(PtVoice *voice,double amount);
void pt_voice_tick(PtVoice *voice,SdVoice *dna,double output[2]);
#endif

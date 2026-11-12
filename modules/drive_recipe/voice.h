#ifndef VSL_DRIVE_RECIPE_VOICE_H
#define VSL_DRIVE_RECIPE_VOICE_H
#include "shape.h"
#include "sound_dna/oscillator.h"
typedef struct {
    const DrcBank *bank;
    const SaBank *dna_bank;
    SdTexture texture[SA_MAX_ANCHORS];
    SdOscillator oscillator[SA_MAX_ANCHORS];
    double amount,target,follow;
    uint64_t frame;
} DrcVoice;
typedef struct {double raw[2],output[2],support;} DrcFrame;
int drc_voice_init(DrcVoice *voice,const DrcBank *bank,const SaBank *dna,
                   const DrsBank *detail,uint64_t seed,double amount);
int drc_voice_set(DrcVoice *voice,double amount);
/* Called after main sample; sampled_phase is its PRE-sample radians. The main
   voice supplies root/detail/fraction timing. No RPM or phase accumulator here. */
int drc_voice_tick(DrcVoice *voice,const SaVoice *dna,double sampled_phase,DrcFrame *frame);
#endif

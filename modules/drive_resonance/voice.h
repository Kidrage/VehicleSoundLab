#ifndef VSL_DRIVE_RESONANCE_VOICE_H
#define VSL_DRIVE_RESONANCE_VOICE_H
#include "bank.h"
#include "dna_atlas/voice.h"
#include "resonant_detail/voice.h"
typedef struct {
    const DrsBank *bank;
    RdtVoice voice[SA_MAX_ANCHORS];
    double amount,target,follow;
    uint64_t frame;
} DrsVoice;
typedef struct {double raw[2],output[2],support;} DrsFrame;
/* Non-RT prewarms all configured filters; bank must outlive voice. */
int drs_voice_init(DrsVoice *voice,const DrsBank *bank,const SaBank *dna,uint64_t seed,double amount);
int drs_voice_set(DrsVoice *voice,double amount);
/* RT: consume the phase actually sampled BEFORE sa_voice_tick_body, and the
   resulting root/blend AFTER it. No independent RPM clock. All configured
   filters/RNGs advance even when muted or outside local support. */
int drs_voice_tick(DrsVoice *voice,const SaVoice *dna,double sampled_phase,DrsFrame *frame);
#endif

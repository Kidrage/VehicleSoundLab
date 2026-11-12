#ifndef VSL_RESONANT_DETAIL_VOICE_H
#define VSL_RESONANT_DETAIL_VOICE_H
#include "profile.h"
#include "filter.h"
#include "excitation.h"
typedef struct {
    const RdtProfile *profile;
    RdtFilter filter[RDT_MAX_BANDS];
    RdtExcitation excitation[RDT_MAX_BANDS];
    uint64_t frame;
} RdtVoice;
/* Init validates before mutation; call on a non-audio thread. */
int rdt_voice_init(RdtVoice *voice,const RdtProfile *profile,uint64_t seed);
/* RT: caller supplies source phase[0,1), preallocated outputs; no I/O/alloc.
   Optional bands[] receives unit-gain mono band signals before stereo mix.
   Reject invalid phase without mutating voice or outputs. */
int rdt_voice_tick(RdtVoice *voice,double phase_cycles,double stereo[2],double bands[RDT_MAX_BANDS]);
#endif

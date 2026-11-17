#ifndef VSL_STATE_DNA_API_H
#define VSL_STATE_DNA_API_H
#include "dna_atlas/voice.h"
#define SX_STATES 4
#define SX_PHASE_NODES (2*SA_MAX_ANCHORS)
enum {SX_BASE,SX_IDLE,SX_POWER,SX_OVERRUN};
typedef struct {
    const SaBank *base,*donor[SX_STATES-1];
    double transition_seconds;
    unsigned mask,nodes[SX_STATES-1];
    double root[SX_STATES-1][SX_PHASE_NODES];
    double delta[SX_STATES-1][SX_PHASE_NODES][SD_MAX_HARMONICS][2];
    double origin[SX_STATES-1];
} SxBank;
typedef struct {
    const SxBank *bank;
    SdTexture texture[SX_STATES-1][SA_MAX_ANCHORS];
    double weight[SX_STATES],target[SX_STATES],follow;
    int coverage[SX_STATES];
    uint64_t frame;
} SxVoice;
typedef struct {
    unsigned available_mask;
    double weight[SX_STATES],target[SX_STATES];
    int coverage[SX_STATES];
} SxTelemetry;
/* Non-RT, banks borrowed immutable. Full H retained and equal across banks.
   align_orders fits arbitrary cycle origins, not physical engine timing. */
int sx_bank_init(SxBank *out,const SaBank *base,const SaBank *const *donors,
                 unsigned align_orders,double transition_seconds);
int sx_voice_init(SxVoice *voice,const SxBank *bank,uint64_t seed);
int sx_voice_select(SxVoice *voice,unsigned state);
/* RT: shares/advances the supplied main SaVoice clock, exactly once. */
int sx_voice_tick(SxVoice *voice,SaVoice *main,const HbBand *band,double stereo[2],double body[2]);
int sx_voice_telemetry(const SxVoice *voice,SxTelemetry *out);
#endif

#ifndef VSL_DNA_ATLAS_BANK_H
#define VSL_DNA_ATLAS_BANK_H
#include "dsp_support/config.h"
#include "profile.h"

#ifndef SA_MAX_ANCHORS
#define SA_MAX_ANCHORS 8
#endif
#define SA_TABLE_SIZE 4096

typedef struct {
    const SdProfile *profile[SA_MAX_ANCHORS]; /* Borrowed; immutable after init. */
    unsigned count, harmonics;
    float offset[SA_MAX_ANCHORS]; /* Common L/R cycle origin, radians. */
    float phase[SA_MAX_ANCHORS][SD_MAX_HARMONICS][2];
    float unit[SA_MAX_ANCHORS][SD_MAX_HARMONICS][4];
    float delta[(SA_MAX_ANCHORS>1)?SA_MAX_ANCHORS-1:1][SD_MAX_HARMONICS][2];
#ifndef VSL_FIXED_V10
    float sine[SA_TABLE_SIZE+1];
#endif
} SaBank;

/* Non-realtime, transactional; sorted base_hz, same harmonic count and codec.
   align_orders=0 preserves original origins; 1..32 fits adjacent low orders.
   This aligns an arbitrary cycle origin, not physical engine banks or timing. */
int sa_bank_init(SaBank *bank, const SdProfile *const *profiles, unsigned count, unsigned align_orders);
/* Explicit opt-in: same full validation/alignment, base5..1000Hz, without
   legacy H*base*1.1 guard. Use only with SaVoice's actual-root19.2..21.6kHz
   carrier taper; this does not enable high-root owned presets/take loading. */
int sa_bank_init_bandlimited(SaBank *bank, const SdProfile *const *profiles, unsigned count, unsigned align_orders);
float sa_bank_sine(const SaBank *bank, float radians);
#endif

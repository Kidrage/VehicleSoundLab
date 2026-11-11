#ifndef VSL_DNA_ATLAS_BANK_H
#define VSL_DNA_ATLAS_BANK_H
#include "profile.h"

#define SA_MAX_ANCHORS 8
#define SA_TABLE_SIZE 4096

typedef struct {
    const SdProfile *profile[SA_MAX_ANCHORS]; /* Borrowed; immutable after init. */
    unsigned count, harmonics;
    double offset[SA_MAX_ANCHORS]; /* Common L/R cycle origin, radians. */
    double phase[SA_MAX_ANCHORS][SD_MAX_HARMONICS][2];
    double unit[SA_MAX_ANCHORS][SD_MAX_HARMONICS][4];
    double delta[SA_MAX_ANCHORS-1][SD_MAX_HARMONICS][2];
    double sine[SA_TABLE_SIZE+1];
} SaBank;

/* Non-realtime, transactional; sorted base_hz, same harmonic count and codec.
   align_orders=0 preserves original origins; 1..32 fits adjacent low orders.
   This aligns an arbitrary cycle origin, not physical engine banks or timing. */
int sa_bank_init(SaBank *bank, const SdProfile *const *profiles, unsigned count, unsigned align_orders);
double sa_bank_sine(const SaBank *bank, double radians);
#endif

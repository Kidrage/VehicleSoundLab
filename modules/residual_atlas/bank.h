#ifndef VSL_RESIDUAL_ATLAS_BANK_H
#define VSL_RESIDUAL_ATLAS_BANK_H
#include "sound_residual/profile.h"
#define RA_MAX_ANCHORS 8
typedef struct {
    unsigned count;
    double root[RA_MAX_ANCHORS];
    SrProfile profile[RA_MAX_ANCHORS]; /* Owned copies; no profile lifetimes. */
} RaBank;
/* Non-realtime, transactional. All anchors share fixed frequency bands and
   density; root selects spectral colour, never transposes those carriers. */
int ra_bank_init(RaBank *bank,const SrProfile *const *profiles,const double *roots,unsigned count);
int ra_bank_valid(const RaBank *bank);
#endif

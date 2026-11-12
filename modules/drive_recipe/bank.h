#ifndef VSL_DRIVE_RECIPE_BANK_H
#define VSL_DRIVE_RECIPE_BANK_H
#include "dna_atlas/voice.h"
#include "drive_resonance/bank.h"
#include "resonant_source/recipe.h"
typedef struct {
    unsigned count,has_low[SA_MAX_ANCHORS];
    double root[SA_MAX_ANCHORS],scale[SA_MAX_ANCHORS];
    double outer_low,inner_low,inner_high,outer_high;
    RssColour colour[SA_MAX_ANCHORS];
    double reduction[SA_MAX_ANCHORS][SD_MAX_HARMONICS];
    SdProfile low[SA_MAX_ANCHORS];
} DrcBank;
/* Non-RT, transactional, owns optional low profiles and compiled power masks.
   Every reduction needs a matching continuous-detail anchor. No new fitting. */
int drc_bank_init(DrcBank *out,const SaBank *dna,const DrsBank *detail,
    const RssColour *colour,const SdProfile *const *low,const double *scale);
int drc_bank_valid(const DrcBank *bank,const SaBank *dna,const DrsBank *detail);
#endif

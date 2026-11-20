#ifndef VSL_DRIVE_RECIPE_BANK_H
#define VSL_DRIVE_RECIPE_BANK_H
#include "dna_atlas/voice.h"
#include "drive_resonance/bank.h"
#include "resonant_source/recipe.h"
#ifdef VSL_FIXED_V10
/* The fixed LF asset contains seven orders. Retain every coefficient and the
   original field semantics, with no reservation for unused main-DNA orders. */
#define DRC_LOW_HARMONICS 7
typedef struct {
    unsigned rate,window,hop,harmonics,components;
    float base_hz;
    float rho[SD_MAX_COMPONENTS];
    SdHarmonic harmonic[DRC_LOW_HARMONICS];
} DrcLowProfile;
#else
typedef SdProfile DrcLowProfile;
#endif

typedef struct {
    unsigned count,has_low[SA_MAX_ANCHORS];
    float root[SA_MAX_ANCHORS],scale[SA_MAX_ANCHORS];
    float outer_low,inner_low,inner_high,outer_high;
    RssColour colour[SA_MAX_ANCHORS];
    float reduction[SA_MAX_ANCHORS][SD_MAX_HARMONICS];
    DrcLowProfile low[SA_MAX_ANCHORS];
} DrcBank;
/* Non-RT, transactional, owns optional low profiles and compiled power masks.
   Every reduction needs a matching continuous-detail anchor. No new fitting. */
int drc_bank_init(DrcBank *out,const SaBank *dna,const DrsBank *detail,
    const RssColour *colour,const SdProfile *const *low,const float *scale);
int drc_bank_valid(const DrcBank *bank,const SaBank *dna,const DrsBank *detail);
#endif

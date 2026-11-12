#ifndef VSL_DRIVE_RESONANCE_BANK_H
#define VSL_DRIVE_RESONANCE_BANK_H
#include "dna_atlas/bank.h"
#include "resonant_detail/profile.h"
typedef struct {
    unsigned count,enabled[SA_MAX_ANCHORS];
    double root[SA_MAX_ANCHORS];
    double outer_low,inner_low,inner_high,outer_high; /* Ratios, not measured RPM coverage. */
    RdtProfile profile[SA_MAX_ANCHORS]; /* Owned fixed-Hz parameters, no PCM. */
} DrsBank;
/* Non-RT, transactional. NULL entries mean missing evidence, never nearest fill.
   Caller keeps recording context consistent; a matching root alone proves no context. */
int drs_bank_init(DrsBank *out,const SaBank *dna,const RdtProfile *const *profiles);
int drs_bank_valid(const DrsBank *bank,const SaBank *dna);
#endif

#ifndef VSL_DRIVE_RESONANCE_BANK_H
#define VSL_DRIVE_RESONANCE_BANK_H
#include "dna_atlas/bank.h"
#include "resonant_detail/profile.h"
#include "stereo_resonance/profile.h"

typedef enum { DRS_NONE, DRS_RDT, DRS_STEREO } DrsKind;
typedef struct {
    unsigned count,enabled[SA_MAX_ANCHORS],kind[SA_MAX_ANCHORS];
    double root[SA_MAX_ANCHORS];
    double outer_low,inner_low,inner_high,outer_high; /* Ratios, not measured RPM coverage. */
    RdtProfile profile[SA_MAX_ANCHORS]; /* Owned fixed-Hz parameters, no PCM. */
    RvsProfile stereo[SA_MAX_ANCHORS]; /* Owned joint-channel parameters/certificates. */
} DrsBank;
/* Non-RT, transactional. NULL entries mean missing evidence, never nearest fill.
   Caller keeps recording context consistent; a matching root alone proves no context. */
int drs_bank_init(DrsBank *out,const SaBank *dna,const RdtProfile *const *profiles);
int drs_bank_init_stereo(DrsBank *out,const SaBank *dna,const RvsProfile *const *profiles);
/* At most one kernel per anchor. Either array may be NULL; both entries NULL
   leave a gap. Non-RT heap scratch avoids multi-megabyte stack temporaries. */
int drs_bank_init_mixed(DrsBank *out,const SaBank *dna,const RdtProfile *const *rdt,const RvsProfile *const *stereo);
int drs_bank_valid(const DrsBank *bank,const SaBank *dna);
#endif

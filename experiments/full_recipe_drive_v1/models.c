#include "models.h"
#include <stdlib.h>
int fr_models_load(FrModels *out) {
    FrModels *m;int ok=0;RssColour colour={.35,1200,1900};double scale=1.6658265329883064;
    const SdProfile *dna[1],*low[1];const RdtProfile *detail[1];
    if(!out)return 0;m=calloc(1,sizeof *m);if(!m)return 0;
    dna[0]=&m->dna;low[0]=&m->low;detail[0]=&m->detail;
    if(!sd_profile_load("voices/dna_bank_v1/V10 Exterior.model",&m->dna)||
       !sd_profile_load("voices/coherent_low_v1/measured_phase.model",&m->low)||
       !rdt_profile_load("voices/resonant_detail_c_v1/moving_35.rdetail",&m->detail)||
       !sa_bank_init(&m->bank,dna,1,0)||!drs_bank_init(&m->resonance,&m->bank,detail)||
       !drc_bank_init(&m->recipe,&m->bank,&m->resonance,&colour,low,&scale))goto done;
    *out=*m;out->bank.profile[0]=&out->dna;ok=1;
done:free(m);return ok;
}

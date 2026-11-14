#include "decel_models.h"
#include "stereo_resonance_io/profile.h"
#include <stdlib.h>
int cdm_models_load(CdmModels *out) {
    CdmModels *m;const SdProfile *dna[1];const RvsProfile *detail[1];
    RssColour colour={.35,1200,1900};int ok=0;
    if(!out)return 0;m=calloc(1,sizeof *m);if(!m)return 0;
    if(!sd_profile_load("voices/E_decel_source_v1/E slowing cabin.model",&m->dna)||
       !rvs_profile_load("voices/E_decel_source_v1/E slowing cabin.sres",&m->detail))goto done;
    dna[0]=&m->dna;detail[0]=&m->detail;
    if(!sa_bank_init(&m->bank,dna,1,0)||!drs_bank_init_stereo(&m->resonance,&m->bank,detail)||
       !drc_bank_init(&m->recipe,&m->bank,&m->resonance,&colour,NULL,NULL))goto done;
    *out=*m;out->bank.profile[0]=&out->dna;ok=1;
done:free(m);return ok;
}

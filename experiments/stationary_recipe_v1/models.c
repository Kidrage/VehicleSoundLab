#include "models.h"
#include "resonant_detail_io/profile.h"
#include <stdlib.h>
int srm_models_load(SrmModels *out) {
    static const char *names[]={"Low","Lower Mid","Upper Mid","High"};
    SrmModels *m;const SdProfile *dna[4];const RdtProfile *detail[4]={0};
    RssColour colour[4]={{0,1200,1900},{.35,1200,1900},{.35,1200,1900},{.35,1200,1900}};
    char path[512];int ok=0;
    if(!out)return 0;m=calloc(1,sizeof *m);if(!m)return 0;
    for(unsigned i=0;i<4;++i) {
        snprintf(path,sizeof path,"voices/exterior_anchors_v1/A Stationary %s.model",names[i]);
        if(!sd_profile_load(path,m->dna+i))goto done;dna[i]=m->dna+i;
        if(i) {
            snprintf(path,sizeof path,"voices/stationary_recipe_v1/A Stationary %s.rdetail",names[i]);
            if(!rdt_profile_load(path,m->detail+i-1))goto done;detail[i]=m->detail+i-1;
        }
    }
    if(!sa_bank_init(&m->bank,dna,4,32)||!drs_bank_init(&m->resonance,&m->bank,detail)||
       !drc_bank_init(&m->recipe,&m->bank,&m->resonance,colour,NULL,NULL))goto done;
    *out=*m;for(unsigned i=0;i<4;++i)out->bank.profile[i]=out->dna+i;ok=1;
done:free(m);return ok;
}

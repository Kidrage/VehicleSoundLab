#include "models.h"
#include "resonant_detail_io/profile.h"
#include <stdlib.h>
int sbm_models_load(SbmModels *out) {
    static const char *names[]={"A Stationary Low","A Stationary Lower Mid",
        "A Bridge Mid Two","A Stationary Upper Mid","A Stationary High"};
    SbmModels *m;const SdProfile *dna[5];const RdtProfile *detail[5]={0};
    RssColour colour[5]={{0,1200,1900},{.35,1200,1900},{.35,1200,1900},
                       {.35,1200,1900},{.35,1200,1900}};
    char path[512];int ok=0;
    if(!out)return 0;m=calloc(1,sizeof *m);if(!m)return 0;
    for(unsigned i=0;i<5;++i) {
        snprintf(path,sizeof path,"voices/%s/%s.model",i==2?"stationary_bridge_v1":"exterior_anchors_v1",names[i]);
        if(!sd_profile_load(path,m->dna+i))goto done;dna[i]=m->dna+i;
        if(i) {
            snprintf(path,sizeof path,"voices/%s/%s.rdetail",i==2?"stationary_bridge_v1":"stationary_recipe_v1",names[i]);
            if(!rdt_profile_load(path,m->detail+i-1))goto done;detail[i]=m->detail+i-1;
        }
    }
    if(!sa_bank_init(&m->bank,dna,5,32)||!drs_bank_init(&m->resonance,&m->bank,detail)||
       !drc_bank_init(&m->recipe,&m->bank,&m->resonance,colour,NULL,NULL))goto done;
    *out=*m;for(unsigned i=0;i<5;++i)out->bank.profile[i]=out->dna+i;ok=1;
done:free(m);return ok;
}

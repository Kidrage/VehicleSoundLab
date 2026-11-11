#include "models.h"
#include <stdlib.h>
int am_models_bank(const AmModels *m,SaBank *bank) {
    const SdProfile *profiles[SA_MAX_ANCHORS];unsigned i;
    if(!m||!bank||m->count<1||m->count>SA_MAX_ANCHORS)return 0;
    for(i=0;i<m->count;++i)profiles[i]=&m->profile[i];
    return sa_bank_init(bank,profiles,m->count,32);
}
int am_models_load(AmModels *destination,int index) {
    static const char *exterior[]={"voices/exterior_anchors_v1/A Stationary Low.model",
        "voices/exterior_anchors_v1/A Stationary Lower Mid.model","voices/exterior_anchors_v1/A Stationary Upper Mid.model",
        "voices/exterior_anchors_v1/A Stationary High.model"};
    static const char *cabin[]={"voices/cabin_anchors_v1/E Cabin Lower.model","voices/cabin_anchors_v1/E Cabin Upper.model"};
    AmModels *candidate;SaBank *trial;unsigned i;int ok=0;
    if(!destination||index<0||index>1)return 0;
    candidate=calloc(1,sizeof *candidate);trial=malloc(sizeof *trial);
    if(!candidate||!trial)goto done;
    candidate->count=index==0?4u:2u;
    for(i=0;i<candidate->count;++i)if(!sd_profile_load(index==0?exterior[i]:cabin[i],&candidate->profile[i]))goto done;
    if(am_models_bank(candidate,trial)){*destination=*candidate;ok=1;}
done:
    free(candidate);free(trial);return ok;
}

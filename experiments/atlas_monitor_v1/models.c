#include "models.h"
#include "io/file.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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
    SrProfile detail[RA_MAX_ANCHORS];const SrProfile *detail_ptr[RA_MAX_ANCHORS];double roots[RA_MAX_ANCHORS];
    if(!destination||index<0||index>1)return 0;
    candidate=calloc(1,sizeof *candidate);trial=malloc(sizeof *trial);
    if(!candidate||!trial)goto done;
    candidate->count=index==0?4u:2u;
    for(i=0;i<candidate->count;++i) {
        const char *path=index==0?exterior[i]:cabin[i],*name=strrchr(path,'/');char residual_path[512];FILE *stream;int read_ok;
        if(!sd_profile_load(path,&candidate->profile[i]))goto done;
        if(!name||snprintf(residual_path,sizeof residual_path,"voices/residual_atlas_v1/%.*s.residual",(int)(strlen(name+1)-6),name+1)>=(int)sizeof residual_path)goto done;
        stream=vsl_fopen(residual_path,"rb");if(!stream)goto done;
        read_ok=sr_profile_read(stream,&detail[i]);if(fclose(stream))read_ok=0;
        if(!read_ok)goto done;
        roots[i]=candidate->profile[i].base_hz;detail_ptr[i]=&detail[i];
    }
    if(!ra_bank_init(&candidate->residual,detail_ptr,roots,candidate->count))goto done;
    if(am_models_bank(candidate,trial)){*destination=*candidate;ok=1;}
done:
    free(candidate);free(trial);return ok;
}

#include "models.h"
#include "modal_source/io.h"
#include "resonant_detail_io/profile.h"
#include <string.h>
int mi_models_valid(const MiModels *m) {
    unsigned i;
    if(!m||!ms_profile_valid(&m->modal)||!rdt_profile_valid(&m->detail))return 0;
    /* Rdt requires a reference base_hz in its file format. This host has no
       shared clock, so never consume a periodic envelope through phase0. */
    for(i=0;i<m->detail.count;++i)if(m->detail.band[i].envelope_order)return 0;
    return 1;
}
int mi_models_load(MiModels *out,const char *modal_path,const char *detail_path) {
    MiModels m;
    if(!out)return 0;
    memset(&m,0,sizeof m);
    if(!ms_profile_load(modal_path,&m.modal)||!rdt_profile_load(detail_path,&m.detail)||!mi_models_valid(&m))return 0;
    *out=m;return 1;
}

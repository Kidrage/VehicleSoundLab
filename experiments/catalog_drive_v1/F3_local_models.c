#include "F3_local_models.h"
#include <stdlib.h>
int f3l_models_load(F3lModels *out,unsigned group) {
    static const char *paths[2][3]={
        {"voices/F3_fifth_local_v1/first_early.model","voices/F3_fifth_local_v1/first_mid.model","voices/F3_fifth_local_v1/first_late.model"},
        {"voices/F3_fifth_local_v1/second_early.model","voices/F3_fifth_local_v1/second_mid.model","voices/F3_fifth_local_v1/second_late.model"}
    };
    F3lModels *m;const SdProfile *profiles[3];int ok=0;
    if(!out||group>1)return 0;
    m=calloc(1,sizeof *m);if(!m)return 0;
    for(unsigned i=0;i<3;++i) {
        if(!sd_profile_load_bandlimited(paths[group][i],m->dna+i))goto done;
        profiles[i]=m->dna+i;
    }
    if(!sa_bank_init_bandlimited(&m->bank,profiles,3,32))goto done;
    *out=*m;
    for(unsigned i=0;i<3;++i)out->bank.profile[i]=out->dna+i;
    ok=1;
done:free(m);return ok;
}

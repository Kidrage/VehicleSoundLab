#include "profile.h"
int spm_profile_valid(const SpmProfile *p) {
    unsigned i,used[MT_MAX_MODES]={0};
    if(!p||!sf_profile_valid(p->spectral)||!mt_profile_valid(p->motion))return 0;
    for(i=0;i<p->spectral->count;++i) {
        if(p->map[i]>p->motion->count)return 0;
        if(p->map[i])used[p->map[i]-1]=1;
    }
    for(i=0;i<p->motion->count;++i)if(!used[i])return 0;
    return 1;
}

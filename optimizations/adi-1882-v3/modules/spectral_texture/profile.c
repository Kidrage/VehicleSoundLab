#include "profile.h"
#include <math.h>
int sf_profile_valid(const SfProfile *p) {
    unsigned b,n;
    if(!p||p->rate!=48000||!p->count||p->count>SF_MAX_BANDS||p->warmup_frames>480000)return 0;
    for(b=0;b<p->count;++b) {
        const SfBand *m=p->band+b;
        if(m->decimation!=0&&m->decimation!=1&&m->decimation!=8)return 0;
        if(!m->count||m->count>PF_MAX_TAPS||!isfinite(m->gain)||m->gain<0||m->gain>4||
           !isfinite(m->right_over_left)||fabsf(m->right_over_left)>4)return 0;
        for(n=0;n<m->count;++n){float x=m->taps[n];if(!isfinite(x)||fabsf(x)>64)return 0;}
    }
    return 1;
}

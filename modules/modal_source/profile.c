#include "profile.h"
#include <math.h>
int ms_profile_valid(const MsProfile *p) {
    unsigned k,c;double last=0,total[2]={0,0};
    if(!p||p->rate!=MS_RATE||!p->count||p->count>MS_MAX_MODES)return 0;
    for(k=0;k<p->count;++k) {
        const MsMode *m=p->mode+k;
        if(!isfinite(m->hz)||m->hz<=last||m->hz>21600)return 0;
        last=m->hz;
        for(c=0;c<2;++c) {
            if(!isfinite(m->amplitude[c])||m->amplitude[c]<0||m->amplitude[c]>4||
               !isfinite(m->phase[c])||fabs(m->phase[c])>1000000)return 0;
            total[c]+=m->amplitude[c];
        }
    }
    return total[0]<=16&&total[1]<=16;
}

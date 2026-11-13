#include "profile.h"
#include <math.h>
int mt_profile_valid(const MtProfile *p) {
    unsigned i,j;
    if(!p||p->rate!=MT_RATE||!p->count||p->count>MT_MAX_MODES||
       !p->hop_frames||p->hop_frames>480000||!isfinite(p->alpha)||p->alpha<0||p->alpha>.98)return 0;
    for(i=0;i<p->count;++i) {
        double power=0;
        for(j=0;j<p->count;++j) {
            double f=p->factor[i][j];
            if(!isfinite(f)||fabs(f)>.25)return 0;
            power+=f*f;
        }
        if(power>.25*.25)return 0;
    }
    return 1;
}

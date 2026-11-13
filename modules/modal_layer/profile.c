#include "profile.h"
#include <math.h>
int ml_profile_valid(const MlProfile *p) {
    unsigned i;
    if(!p||!ms_profile_valid(p->modal)||!rdt_profile_valid(p->detail)||
       !isfinite(p->modal_ratio)||p->modal_ratio<.25||p->modal_ratio>4||
       !isfinite(p->modal_gain)||p->modal_gain<0||p->modal_gain>1||
       !isfinite(p->detail_gain)||p->detail_gain<0||p->detail_gain>1||
       !isfinite(p->level_gain)||p->level_gain<0||p->level_gain>8||
       !p->attack_frames||p->attack_frames>480000||!p->release_frames||p->release_frames>480000)return 0;
    for(i=0;i<p->detail->count;++i)if(p->detail->band[i].envelope_order)return 0;
    return 1;
}

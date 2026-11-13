#include "profile.h"
#include <math.h>
int fi_profile_valid(const FiProfile *p) {
    return p&&ms_profile_valid(p->modal)&&mt_profile_valid(p->motion)&&sf_profile_valid(p->detail)&&
        p->modal->count==p->motion->count&&isfinite(p->modal_ratio)&&p->modal_ratio>=.25&&p->modal_ratio<=4&&
        isfinite(p->modal_gain)&&p->modal_gain>=0&&p->modal_gain<=1&&
        isfinite(p->detail_gain)&&p->detail_gain>=0&&p->detail_gain<=4&&
        isfinite(p->level_gain)&&p->level_gain>=0&&p->level_gain<=8&&
        p->attack_frames>=1&&p->attack_frames<=480000&&p->release_frames>=1&&p->release_frames<=480000;
}

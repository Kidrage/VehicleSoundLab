#include "types.h"
#include <math.h>
int vi_valid(const ViInput *p) {
    if(!p||(p->source!=VI_INTERNAL&&p->source!=VI_EXTERNAL)||
       (p->valid&~(VI_SPEED|VI_ACCELERATION|VI_SLIP)))return 0;
    if(!isfinite(p->speed_mps)||p->speed_mps<0||p->speed_mps>120||
       !isfinite(p->acceleration_mps2)||fabsf(p->acceleration_mps2)>30||
       !isfinite(p->tire_slip)||p->tire_slip<0||p->tire_slip>1)return 0;
    if(p->source==VI_EXTERNAL)return (p->valid&(VI_SPEED|VI_ACCELERATION))==(VI_SPEED|VI_ACCELERATION);
    return !(p->valid&(VI_SPEED|VI_ACCELERATION));
}

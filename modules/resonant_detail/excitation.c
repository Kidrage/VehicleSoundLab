#include "excitation.h"
#include <math.h>
static double uniform(RdtExcitation *p) {
    uint64_t x=p->state;
    x^=x>>12;x^=x<<25;x^=x>>27;p->state=x;
    return (((x*UINT64_C(2685821657736338717))>>11)+.5)/9007199254740992.;
}
void rdt_excitation_init(RdtExcitation *p,uint64_t seed) { p->state=seed?seed:1;p->spare=0;p->has_spare=0; }
double rdt_excitation_next(RdtExcitation *p) {
    double radius,angle;
    if(p->has_spare){p->has_spare=0;return p->spare;}
    radius=sqrt(-2*log(uniform(p)));angle=6.28318530717958647692*uniform(p);
    p->spare=radius*sin(angle);p->has_spare=1;return radius*cos(angle);
}

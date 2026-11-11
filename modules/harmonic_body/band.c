#include "band.h"
#include <math.h>
static double ease(double x) { return x*x*(3-2*x); }
HbBand hb_band_default(void) { HbBand b={20,35,180,350};return b; }
int hb_band_valid(const HbBand *b) {
    return b&&isfinite(b->stop_low)&&isfinite(b->pass_low)&&isfinite(b->pass_high)&&isfinite(b->stop_high)&&
        b->stop_low>=0&&b->stop_low<b->pass_low&&b->pass_low<=b->pass_high&&b->pass_high<b->stop_high&&b->stop_high<=1000;
}
double hb_band_weight(const HbBand *b,double hz) {
    if(hz<=b->stop_low||hz>=b->stop_high)return 0;
    if(hz<b->pass_low)return ease((hz-b->stop_low)/(b->pass_low-b->stop_low));
    if(hz>b->pass_high)return 1-ease((hz-b->pass_high)/(b->stop_high-b->pass_high));
    return 1;
}

#include "band.h"
#include <math.h>
HbBand hb_band_default(void) { HbBand b={20,35,180,350};return b; }
int hb_band_valid(const HbBand *b) {
    return b&&isfinite(b->stop_low)&&isfinite(b->pass_low)&&isfinite(b->pass_high)&&isfinite(b->stop_high)&&
        b->stop_low>=0&&b->stop_low<b->pass_low&&b->pass_low<=b->pass_high&&b->pass_high<b->stop_high&&b->stop_high<=1000;
}
float hb_band_weight(const HbBand *b,float hz) {
    return hb_band_weight_inline(b,hz);
}

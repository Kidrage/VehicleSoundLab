#include "firing.h"
#include "core/types.h"
/* 5.2 common-pin V10 family: alternating 90/54 crank degrees, 144 per bank.
   Audi official 5.2 FSI engine description confirms 54/90, unlike a split-pin
   5.0 V10's even 72. First-bank origin/orientation is a modelling convention;
   this is not a measured Huracan pressure trace or manifold transfer model. */
static const double v10_common_pin[]={0,90,144,234,288,378,432,522,576,666};
double vsl_firing_degrees(int profile,int event,int cylinders) {
    if(cylinders<1 || event<0 || event>=cylinders)return 0;
    if(profile==VSL_V10 && cylinders==10)return v10_common_pin[event];
    return 720.0*event/cylinders;
}
double vsl_bank_offset_cycles(int profile) {
    return profile==VSL_V10?90.0/144.0:.5;
}

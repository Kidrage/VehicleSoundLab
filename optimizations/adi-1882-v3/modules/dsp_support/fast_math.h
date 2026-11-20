#ifndef VSL_DSP_FAST_MATH_H
#define VSL_DSP_FAST_MATH_H
#include <math.h>
#ifdef VSL_DSP_FAST_TRIG
#include "fast_trig.h"
#endif
/* Common audio phases lie in one neighboring period. For these cases the
   exact fmodf remainder is either the original float or one subtraction.
   Keep libm for larger arguments, nonpositive divisors and exceptional input.
   Negative multiples retain the required negative zero. */
static inline float vsl_bounded_fmodf(float x,float y){
    if(y>0){
        if(x>=0){if(x<y)return x;if(x<2*y)return x-y;}
        else {if(x> -y)return x;if(x> -2*y)return -(-x-y);}
    }
    return fmodf(x,y);
}
#define fmodf vsl_bounded_fmodf
#endif

#include "noise.h"
#include "normal_table.h"
#include <math.h>
float vsl_normal(uint64_t *state) {
    uint32_t x=(uint32_t)*state^(uint32_t)(*state>>32),bits;
    float z;
    if(!x)x=UINT32_C(0x6d2b79f5);
    x^=x<<13;x^=x>>17;x^=x<<5;*state=x;
    bits=x&UINT32_C(0x7fffffff);
    if(bits<UINT32_C(2146959360)) {
        float p=(float)bits*(4097.000244200244f/2147483648.f);
        unsigned i=(unsigned)p;
        /* FP32 may round the last central position up to the endpoint. */
        z=i>=4096?normal_table[4096]:normal_table[i]+(p-i)*(normal_table[i+1]-normal_table[i]);
    } else {
        float tail=((float)(UINT32_C(2147483647)-bits)+.5f)/4294967296.f;
        float q=sqrtf(-2*logf(tail));
        z=-(((((-.007784894002430293f*q-.3223964580411365f)*q-2.400758277161838f)*q-2.549732539343734f)*q+4.374664141464968f)*q+2.938163982698783f)/
            ((((.007784695709041462f*q+.3224671290700398f)*q+2.445134137142996f)*q+3.754408661907416f)*q+1);
    }
    return x&UINT32_C(0x80000000)?-z:z;
}

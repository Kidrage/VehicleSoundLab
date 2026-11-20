#if defined(VSL_DSP_FAST_TRIG)
#include "fast_trig.h"
#include "storage.h"
#undef sinf
#undef cosf
VSL_SECTION(VSL_L1_STATE)
float vsl_trig_table[VSL_TRIG_SIZE+1];
int vsl_trig_ready;
void vsl_trig_prepare(void){
    unsigned n;if(vsl_trig_ready)return;
    for(n=0;n<VSL_TRIG_SIZE;++n)
        vsl_trig_table[n]=sinf(6.2831853071795864769f*n/VSL_TRIG_SIZE);
    vsl_trig_table[VSL_TRIG_SIZE]=vsl_trig_table[0];vsl_trig_ready=1;
}
#endif

#include "engine.h"
#include "modules.h"
#include <math.h>
#include <string.h>
int vsl_set_ir(VslEngine *e,const float *mono,unsigned n,unsigned sr) {
    unsigned i; double sum=0;
    if(!mono || n<1 || n>VSL_MAX_IR || sr!=(unsigned)e->sample_rate) return 0;
    for(i=0;i<n;++i) { if(!isfinite(mono[i])) return 0; sum+=fabs(mono[i]); }
    if(sum<1e-9) return 0;
    for(i=0;i<n;++i) e->acoustics.ir[i]=(float)(mono[i]/fmax(1,sum));
    e->acoustics.ir_length=n;
    e->acoustics.tap_count=0;
    for(i=0;i<n;++i) if(e->acoustics.ir[i]!=0)
        e->acoustics.taps[e->acoustics.tap_count++]=i;
    memset(e->acoustics.history,0,sizeof e->acoustics.history);
    e->acoustics.cursor=0; return 1;
}
double vsl_ir_tick(VslEngine *e,double x) {
    VslAcoustics *a=&e->acoustics;
    double wet=0;
    unsigned i;
    a->history[a->cursor]=(float)x;
    if(!e->smooth.pure_osc && e->smooth.space>.00001) {
        for(i=0;i<a->tap_count;++i) {
            unsigned t=a->taps[i];
            wet+=a->ir[t]*a->history[(a->cursor+VSL_MAX_IR-t)%VSL_MAX_IR];
        }
    }
    a->cursor=(a->cursor+1)%VSL_MAX_IR;
    x=x*(1-e->smooth.space)+wet*e->smooth.space;
    return x;
}

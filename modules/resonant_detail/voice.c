#include "voice.h"
#include "envelope.h"
#include <math.h>
#include <string.h>
int rdt_voice_init(RdtVoice *v,const RdtProfile *p,uint64_t seed) {
    unsigned b;
    if(!v||!rdt_profile_valid(p))return 0;
    memset(v,0,sizeof *v);v->profile=p;
    for(b=0;b<p->count;++b)rdt_excitation_init(v->excitation+b,seed^(UINT64_C(0x9E3779B97F4A7C15)*(b+1)));
    return 1;
}
int rdt_voice_tick(RdtVoice *v,double phase,double out[2],double bands[RDT_MAX_BANDS]) {
    unsigned b,k,order=0;double left=0,right=0;
    double cosine[RDT_MAX_ENVELOPE],sine[RDT_MAX_ENVELOPE];
    if(!v||!v->profile||!out||!isfinite(phase)||phase<0||phase>=1)return 0;
    /* Every band sees the same phase. Evaluate each exact libm argument once,
       retaining the original cosine-then-sine accumulation order per band. */
    for(b=0;b<v->profile->count;++b)if(v->profile->band[b].envelope_order>order)order=v->profile->band[b].envelope_order;
    for(k=0;k<order;++k){cosine[k]=cos(2*3.14159265358979323846*(k+1)*phase);sine[k]=sin(2*3.14159265358979323846*(k+1)*phase);}
    for(b=0;b<v->profile->count;++b) {
        const RdtBand *m=v->profile->band+b;
        double power=1;
        double x=rdt_filter_source(v->filter+b,m,rdt_excitation_next(v->excitation+b));
        for(k=0;k<m->envelope_order;++k)power+=cosine[k]*m->beta[k];
        for(k=0;k<m->envelope_order;++k)power+=sine[k]*m->beta[m->envelope_order+k];
        x*=sqrt(power);
        x=rdt_filter_post(v->filter+b,m,x);
        if(bands)bands[b]=x;
        left+=x*m->gain;right+=x*(m->gain*m->right_over_left);
    }
    out[0]=left;out[1]=right;++v->frame;return 1;
}

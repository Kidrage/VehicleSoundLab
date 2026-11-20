#include "modules/resonant_detail/voice.h"
#include "modules/resonant_detail/envelope.h"
#include <math.h>
#include <string.h>
int rdt_voice_init(RdtVoice *v,const RdtProfile *p,uint64_t seed) {
    unsigned b,k;
    if(!v||!rdt_profile_valid(p))return 0;
    memset(v,0,sizeof *v);v->profile=p;
    for(b=0;b<p->count;++b){
        rdt_excitation_init(v->excitation+b,seed^(UINT64_C(0x9E3779B97F4A7C15)*(b+1)));
        if(p->band[b].envelope_order){
            for(k=0;k<RDT_ENVELOPE_POINTS;++k)
                v->envelope[b][k]=rdt_envelope_amplitude(p->band+b,(float)k/RDT_ENVELOPE_POINTS);
            v->envelope[b][RDT_ENVELOPE_POINTS]=v->envelope[b][0];
        }
    }
    return 1;
}
int rdt_voice_tick(RdtVoice *v,float phase,float out[2],float bands[RDT_MAX_BANDS]) {
    unsigned b,index;float left=0,right=0,position,u;
    if(!v||!v->profile||!out||!isfinite(phase)||phase<0||phase>=1)return 0;
    position=phase*RDT_ENVELOPE_POINTS;index=(unsigned)position;u=position-index;
    for(b=0;b<v->profile->count;++b) {
        const RdtBand *m=v->profile->band+b;
        float x=rdt_filter_source(v->filter+b,m,rdt_excitation_next(v->excitation+b));
        if(m->envelope_order)x*=v->envelope[b][index]+u*(v->envelope[b][index+1]-v->envelope[b][index]);
        x=rdt_filter_post(v->filter+b,m,x);
        if(bands)bands[b]=x;
        left+=x*m->gain;right+=x*(m->gain*m->right_over_left);
    }
    out[0]=left;out[1]=right;++v->frame;return 1;
}

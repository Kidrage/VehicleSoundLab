#include "voice.h"
#include "resonant_detail/excitation.h"
#include <stdlib.h>
struct SfBank {
    unsigned count,warmup_frames;
    PfKernel *kernel[SF_MAX_BANDS];double gain[SF_MAX_BANDS],right[SF_MAX_BANDS];
};
struct SfVoice {
    const SfBank *bank;unsigned position;uint64_t frame;
    PfState *filter[SF_MAX_BANDS];RdtExcitation excitation[SF_MAX_BANDS];
    double ready[SF_MAX_BANDS][PF_BLOCK],input[PF_BLOCK];
};
void sf_bank_destroy(SfBank *b) {
    unsigned i;if(!b)return;for(i=0;i<b->count;++i)pf_kernel_destroy(b->kernel[i]);free(b);
}
SfBank *sf_bank_create(const SfProfile *p) {
    SfBank *b;unsigned i;if(!sf_profile_valid(p))return NULL;
    b=calloc(1,sizeof *b);if(!b)return NULL;b->count=p->count;b->warmup_frames=p->warmup_frames;
    for(i=0;i<b->count;++i) {
        b->kernel[i]=pf_kernel_create(p->band[i].taps,p->band[i].count);
        if(!b->kernel[i]){sf_bank_destroy(b);return NULL;}
        b->gain[i]=p->band[i].gain;b->right[i]=p->band[i].right_over_left;
    }
    return b;
}
void sf_voice_destroy(SfVoice *v) {
    unsigned i;if(!v)return;for(i=0;i<v->bank->count;++i)pf_state_destroy(v->filter[i]);free(v);
}
SfVoice *sf_voice_create(const SfBank *b,uint64_t seed) {
    SfVoice *v;unsigned i,n;double scratch[2];if(!b)return NULL;
    v=calloc(1,sizeof *v);if(!v)return NULL;v->bank=b;v->position=PF_BLOCK;
    for(i=0;i<b->count;++i) {
        v->filter[i]=pf_state_create(b->kernel[i]);
        if(!v->filter[i]){sf_voice_destroy(v);return NULL;}
        rdt_excitation_init(v->excitation+i,seed^(UINT64_C(0x9E3779B97F4A7C15)*(i+1)));
    }
    for(n=0;n<b->warmup_frames;++n)if(!sf_voice_tick(v,scratch,NULL)){sf_voice_destroy(v);return NULL;}
    v->frame=0;return v;
}
int sf_voice_tick(SfVoice *v,double out[2],double *bands) {
    unsigned b,n;double left=0,right=0;if(!v||!out)return 0;
    if(v->position==PF_BLOCK) {
        for(b=0;b<v->bank->count;++b) {
            for(n=0;n<PF_BLOCK;++n)v->input[n]=rdt_excitation_next(v->excitation+b);
            if(!pf_filter_block(v->filter[b],v->input,v->ready[b]))return 0;
        }
        v->position=0;
    }
    for(b=0;b<v->bank->count;++b) {
        double x=v->ready[b][v->position]*v->bank->gain[b];if(bands)bands[b]=x;
        left+=x;right+=x*v->bank->right[b];
    }
    out[0]=left;out[1]=right;++v->position;++v->frame;return 1;
}
int sf_voice_process(SfVoice *v,double *out,unsigned frames) {
    unsigned n;if(!v||(frames&&!out))return 0;
    for(n=0;n<frames;++n)if(!sf_voice_tick(v,out+2*n,NULL))return 0;return 1;
}

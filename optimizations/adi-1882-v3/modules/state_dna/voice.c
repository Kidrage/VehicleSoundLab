#include "lookup.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
int sx_voice_init(SxVoice *v,const SxBank *b,uint64_t seed) {
    unsigned s,a;if(!v||!b||!b->base||!b->mask||!seed)return 0;
    memset(v,0,sizeof *v);v->bank=b;v->weight[0]=v->target[0]=1;
    v->follow=1-expf(-1/(b->transition_seconds*48000));
    for(s=0;s<SX_STATES-1;++s)if(b->donor[s])for(a=0;a<b->donor[s]->count;++a)
        sd_texture_init(&v->texture[s][a],b->donor[s]->profile[a],seed^((uint64_t)(s+1)*UINT64_C(0x9e3779b97f4a7c15)));
    return 1;
}
int sx_voice_select(SxVoice *v,unsigned state) {
    unsigned s;if(!v||!v->bank||state>=SX_STATES)return 0;
    if(!(v->bank->mask&(1u<<state)))state=SX_BASE;
    for(s=0;s<SX_STATES;++s)v->target[s]=s==state?1.f:0.f;
    return 1;
}
static float delta(const SxBank *b,unsigned s,float root,unsigned h,unsigned c) {
    unsigned lo=0,hi;float t;
    if(root<=b->root[s][0])return b->delta[s][0][h][c];
    if(root>=b->root[s][b->nodes[s]-1])return b->delta[s][b->nodes[s]-1][h][c];
    while(lo+1<b->nodes[s]&&root>b->root[s][lo+1])++lo;hi=lo+1;
    t=(root-b->root[s][lo])/(b->root[s][hi]-b->root[s][lo]);
    return b->delta[s][lo][h][c]+t*(b->delta[s][hi][h][c]-b->delta[s][lo][h][c]);
}
int sx_voice_tick(SxVoice *v,SaVoice *main,const HbBand *band,float out[2],float body[2]) {
    unsigned a,h,c,s,lo[SX_STATES],hi[SX_STATES];float t[SX_STATES];
    float cl,sl,bc,bs;const SxBank *b;
    if(!v||!(b=v->bank)||!main||main->bank!=b->base||!out||!body||out==body||
       !hb_band_valid(band)||v->frame!=main->frame)return 0;
    cl=bc=cosf(main->phase);sl=bs=sinf(main->phase);
    main->root_hz+=main->follow*(main->root_target-main->root_hz);
    main->detail+=main->follow*(main->detail_target-main->detail);main->gain+=main->follow*(main->gain_target-main->gain);
    sd_texture_prepare_batch(main->texture,b->base->profile,b->base->count);
    sx_position(b->base,main->root_hz,&lo[0],&hi[0],&t[0]);
    main->lower=lo[0];main->upper=hi[0];main->blend=t[0];
    for(s=0;s<SX_STATES;++s){
        const SaBank *bank=s?b->donor[s-1]:b->base;
        v->weight[s]+=v->follow*(v->target[s]-v->weight[s]);
        if(!bank){v->coverage[s]=0;continue;}
        if(s){sd_texture_prepare_batch(v->texture[s-1],bank->profile,bank->count);
            sx_position(bank,main->root_hz,&lo[s],&hi[s],&t[s]);}
        v->coverage[s]=main->root_hz<bank->profile[0]->base_hz-1e-8f?-1:
            main->root_hz>bank->profile[bank->count-1]->base_hz+1e-8f?1:0;
    }
    main->coverage=v->coverage[0];out[0]=out[1]=body[0]=body[1]=0;
    for(h=0;h<b->base->harmonics;++h){
        float hz=(h+1)*main->root_hz,aa=1,next,weight=hb_band_weight(band,hz);
        if(hz>=21600)break;
        if(hz>19200){float x=(hz-19200)/2400;aa=1-x*x*(3-2*x);}
        for(c=0;c<2;++c){
            float mag=sx_magnitude(b->base,main->texture,main->detail,lo[0],hi[0],t[0],h,c),base_mag=mag;
            float re=b->base->unit[lo[0]][h][2*c],im=b->base->unit[lo[0]][h][2*c+1];
            float phase=b->base->phase[lo[0]][h][c],change=0;
            if(lo[0]!=hi[0])phase+=t[0]*b->base->delta[lo[0]][h][c];
            for(s=1;s<SX_STATES;++s)if(b->donor[s-1]&&v->weight[s]!=0){
                float m=sx_magnitude(b->donor[s-1],v->texture[s-1],main->detail,lo[s],hi[s],t[s],h,c);
                mag+=v->weight[s]*(m-base_mag);change+=v->weight[s]*delta(b,s-1,main->root_hz,h,c);
            }
            if(change!=0){phase+=change;re=sa_bank_sine(b->base,phase+PI/2);im=sa_bank_sine(b->base,phase);}
            else if(lo[0]!=hi[0]){
                if(t[0]==1){re=b->base->unit[hi[0]][h][2*c];im=b->base->unit[hi[0]][h][2*c+1];}
                else if(t[0]!=0){re=sa_bank_sine(b->base,phase+PI/2);im=sa_bank_sine(b->base,phase);}
            }
            float contribution=aa*mag*(re*cl-im*sl);out[c]+=contribution;
            if(weight!=0)body[c]+=weight*contribution;
        }
        next=sl*bc+cl*bs;cl=cl*bc-sl*bs;sl=next;
    }
    for(c=0;c<2;++c){out[c]*=main->gain;body[c]*=main->gain;}
    main->phase+=2*PI*main->root_hz/48000;if(main->phase>=2*PI)main->phase-=2*PI;
    for(a=0;a<b->base->count;++a)main->texture[a].fraction+=main->root_hz/12000;
    for(s=0;s<SX_STATES-1;++s)if(b->donor[s])for(a=0;a<b->donor[s]->count;++a)
        v->texture[s][a].fraction+=main->root_hz/12000;
    ++main->frame;++v->frame;return 1;
}
int sx_voice_telemetry(const SxVoice *v,SxTelemetry *out) {
    if(!v||!v->bank||!out)return 0;memset(out,0,sizeof *out);out->available_mask=v->bank->mask;
    memcpy(out->weight,v->weight,sizeof v->weight);memcpy(out->target,v->target,sizeof v->target);
    memcpy(out->coverage,v->coverage,sizeof v->coverage);return 1;
}

#include "voice.h"
#include <math.h>
#include <string.h>
static int unit(float x){return isfinite(x)&&x>=0&&x<=1;}
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
int rvs_voice_prepare(RvsVoice *v,float *out,unsigned frames){
    unsigned b,n,i,j,k;
    if(!v||!v->profile||!out||!frames||v->prepared_frames)return 0;
    memset(out,0,2*frames*sizeof *out);
    /* Band-major scheduling keeps one filter and its coefficients hot. Each
       band's RNG streams are independent. The operations within a band, and
       the order of additions to each output sample, remain unchanged. */
    for(b=0;b<v->profile->count;++b){
        const RvsBand *m=v->profile->band+b;
        for(n=0;n<frames;++n){
            float z[2],y[2];
            for(i=0;i<2;++i)z[i]=rdt_excitation_next(&v->excitation[b][i]);
            for(i=0;i<2;++i){
                unsigned at=v->at[b]?v->at[b]-1:m->order-1;
                y[i]=m->noise[i][0]*z[0]+m->noise[i][1]*z[1];
                for(j=0;j<m->order;++j){
                    for(k=0;k<2;++k)y[i]+=m->a[j][i][k]*v->history[b][at][k];
                    at=at?at-1:m->order-1;
                }
            }
            for(i=0;i<2;++i){
                v->history[b][v->at[b]][i]=y[i];
                out[2*n+i]+=m->gain*rdt_filter_post(&v->post[b][i],&m->post,y[i]);
            }
            if(++v->at[b]==m->order)v->at[b]=0;
        }
    }
    for(n=0;n<2*frames;++n)if(!isfinite(out[n]))return 0;
    v->prepared=out;v->prepared_frames=frames;return 1;
}
#endif
int rvs_voice_tick(RvsVoice *v,float out[2],float raw[2]) {
    float sum[2]={0};unsigned b,i,j,k;
    if(!v||!v->profile||!out)return 0;
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
    if(v->prepared_frames){
        sum[0]=v->prepared[0];sum[1]=v->prepared[1];
        v->prepared+=2;--v->prepared_frames;
    }else
#endif
    {
    for(b=0;b<v->profile->count;++b) {
        const RvsBand *m=v->profile->band+b;float z[2],y[2];
        for(i=0;i<2;++i)z[i]=rdt_excitation_next(&v->excitation[b][i]);
        for(i=0;i<2;++i) {
            unsigned at=v->at[b]?v->at[b]-1:m->order-1;
            y[i]=m->noise[i][0]*z[0]+m->noise[i][1]*z[1];
            for(j=0;j<m->order;++j) {
                for(k=0;k<2;++k)y[i]+=m->a[j][i][k]*v->history[b][at][k];
                at=at?at-1:m->order-1;
            }
        }
        for(i=0;i<2;++i) {
            v->history[b][v->at[b]][i]=y[i];
            sum[i]+=m->gain*rdt_filter_post(&v->post[b][i],&m->post,y[i]);
        }
        if(++v->at[b]==m->order)v->at[b]=0;
    }
    }
    v->amount+=v->follow*(v->target-v->amount);
    for(i=0;i<2;++i){if(!isfinite(sum[i]))return 0;if(raw)raw[i]=sum[i];out[i]=sum[i]*v->amount;}
    ++v->frame;return 1;
}
int rvs_voice_init(RvsVoice *v,const RvsProfile *p,uint64_t seed,float amount) {
    unsigned i,j,n;float unused[2];
    if(!v||!unit(amount)||!rvs_profile_valid(p))return 0;
    memset(v,0,sizeof *v);v->profile=p;v->amount=v->target=amount;v->follow=1-expf(-1/(.018f*48000));
    for(i=0;i<p->count;++i)for(j=0;j<2;++j)
        rdt_excitation_init(&v->excitation[i][j],seed^(UINT64_C(0x9e3779b97f4a7c15)*(2*i+j+1)));
    for(n=0;n<p->warmup_frames;++n)if(!rvs_voice_tick(v,unused,NULL))return 0;
    v->frame=0;return 1;
}
int rvs_voice_set(RvsVoice *v,float amount){if(!v||!v->profile||!unit(amount))return 0;v->target=amount;return 1;}

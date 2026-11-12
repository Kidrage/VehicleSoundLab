#include "voice.h"
#include <math.h>
#include <string.h>
static int unit(double x){return isfinite(x)&&x>=0&&x<=1;}
int rvs_voice_tick(RvsVoice *v,double out[2],double raw[2]) {
    double sum[2]={0};unsigned b,i,j,k;
    if(!v||!v->profile||!out)return 0;
    for(b=0;b<v->profile->count;++b) {
        const RvsBand *m=v->profile->band+b;double z[2],y[2];
        for(i=0;i<2;++i)z[i]=rdt_excitation_next(&v->excitation[b][i]);
        for(i=0;i<2;++i) {
            y[i]=m->noise[i][0]*z[0]+m->noise[i][1]*z[1];
            for(j=0;j<m->order;++j) {
                unsigned at=(v->at[b]+m->order-1-j)%m->order;
                for(k=0;k<2;++k)y[i]+=m->a[j][i][k]*v->history[b][at][k];
            }
        }
        for(i=0;i<2;++i) {
            v->history[b][v->at[b]][i]=y[i];
            sum[i]+=m->gain*rdt_filter_post(&v->post[b][i],&m->post,y[i]);
        }
        v->at[b]=(v->at[b]+1)%m->order;
    }
    v->amount+=v->follow*(v->target-v->amount);
    for(i=0;i<2;++i){if(!isfinite(sum[i]))return 0;if(raw)raw[i]=sum[i];out[i]=sum[i]*v->amount;}
    ++v->frame;return 1;
}
int rvs_voice_init(RvsVoice *v,const RvsProfile *p,uint64_t seed,double amount) {
    unsigned i,j,n;double unused[2];
    if(!v||!unit(amount)||!rvs_profile_valid(p))return 0;
    memset(v,0,sizeof *v);v->profile=p;v->amount=v->target=amount;v->follow=1-exp(-1/(.018*48000));
    for(i=0;i<p->count;++i)for(j=0;j<2;++j)
        rdt_excitation_init(&v->excitation[i][j],seed^(UINT64_C(0x9e3779b97f4a7c15)*(2*i+j+1)));
    for(n=0;n<p->warmup_frames;++n)if(!rvs_voice_tick(v,unused,NULL))return 0;
    v->frame=0;return 1;
}
int rvs_voice_set(RvsVoice *v,double amount){if(!v||!v->profile||!unit(amount))return 0;v->target=amount;return 1;}

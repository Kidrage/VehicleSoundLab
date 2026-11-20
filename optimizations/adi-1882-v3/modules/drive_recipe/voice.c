#include "dsp/perf.h"
#include "voice.h"
#include <math.h>
#include <string.h>
#include "dsp_support/storage.h"
#define PI 3.14159265358979323846f
static int unit(float x){return isfinite(x)&&x>=0&&x<=1.3f;}
int drc_voice_init(DrcVoice *out,const DrcBank *b,const SaBank *dna,const DrsBank *detail,uint64_t seed,float amount){
    unsigned a,n,h,c,k;
    float coefficients[SD_MAX_HARMONICS][4];VSL_SECTION(VSL_DDR) VSL_INIT_WORK DrcVoice v;
    (void)seed;
    if(!out||!unit(amount)||!drc_bank_valid(b,dna,detail))return 0;
    memset(&v,0,sizeof v);v.bank=b;v.dna_bank=dna;v.amount=v.target=amount;v.follow=1-expf(-1/(.018f*48000));
    for(a=0;a<b->count;++a)if(b->has_low[a]){
        const SdProfile *low=b->low+a;
        for(h=0;h<low->harmonics;++h)for(c=0;c<2;++c){
            const SdHarmonic *m=low->harmonic+h;
            float re=m->mean[2*c],im=m->mean[2*c+1],variance=0,norm=sqrtf(re*re+im*im),mag;
            for(k=0;k<low->components;++k)variance+=m->basis[k][2*c]*m->basis[k][2*c]+m->basis[k][2*c+1]*m->basis[k][2*c+1];
            for(k=0;k<4;++k)variance+=m->root[2*c][k]*m->root[2*c][k]+m->root[2*c+1][k]*m->root[2*c+1][k];
            /* Match time-averaged order power at the shipped detail=1.
               Keep measured mean phase; remove independent LF random motion. */
            mag=sqrtf(norm*norm+variance);
            coefficients[h][2*c]=mag*(norm>1e-15f?re/norm:1);
            coefficients[h][2*c+1]=mag*(norm>1e-15f?im/norm:0);
        }
        for(n=0;n<1024;++n){float phase=2*PI*n/1024+dna->offset[a];
            for(h=0;h<low->harmonics;++h)for(c=0;c<2;++c){
                const float *z=coefficients[h];
                v.wave[a][n][c]+=z[2*c]*cosf((h+1)*phase)-z[2*c+1]*sinf((h+1)*phase);
            }
        }
    }
    for(a=0;a<b->count;++a)memcpy(v.wave[a][1024],v.wave[a][0],sizeof v.wave[a][0]);
    *out=v;return 1;
}
int drc_voice_set(DrcVoice *v,float amount){if(!v||!v->bank||!unit(amount))return 0;v->target=amount;return 1;}
int drc_voice_tick(DrcVoice *v,const SaVoice *dna,float phase,DrcFrame *f);
int drc_voice_tick_impl(DrcVoice *v,const SaVoice *dna,float phase,DrcFrame *f){
    unsigned a,c,n;float w[SA_MAX_ANCHORS],position,u;
    if(!v||!v->bank||!dna||dna->bank!=v->dna_bank||!f||!isfinite(phase)||phase<0||phase>=2*PI)return 0;
    memset(f,0,sizeof *f);drc_weights(v->bank,dna->root_hz,w);
    position=phase*(1024/(2*PI));n=(unsigned)position;if(n>=1024)n=0;u=position-(unsigned)position;
    for(a=0;a<v->bank->count;++a)if(v->bank->has_low[a]){
        float weight=w[a]*drc_support(v->bank,a,dna->root_hz);f->support+=weight*weight;
        for(c=0;c<2;++c)f->raw[c]+=(v->wave[a][n][c]+u*(v->wave[a][n+1][c]-v->wave[a][n][c]))*v->bank->scale[a]*weight;
    }
    v->amount+=v->follow*(v->target-v->amount);
    for(c=0;c<2;++c)f->output[c]=f->raw[c]*v->amount;++v->frame;return 1;
}
int drc_voice_tick(DrcVoice *v,const SaVoice *dna,float phase,DrcFrame *f){vsl_perf_enter(2);int result=drc_voice_tick_impl(v,dna,phase,f);vsl_perf_leave();return result;}


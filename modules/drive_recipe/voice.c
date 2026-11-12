#include "voice.h"
#include <math.h>
#include <string.h>
#define DRC_PI 3.14159265358979323846
static int unit(double x){return isfinite(x)&&x>=0&&x<=1;}
int drc_voice_init(DrcVoice *out,const DrcBank *b,const SaBank *dna,
                   const DrsBank *detail,uint64_t seed,double amount) {
    unsigned a;DrcVoice v;
    if(!out||!unit(amount)||!drc_bank_valid(b,dna,detail))return 0;
    memset(&v,0,sizeof v);v.bank=b;v.dna_bank=dna;v.amount=v.target=amount;v.follow=1-exp(-1/(.018*48000));
    for(a=0;a<b->count;++a)if(b->has_low[a]) {
        sd_texture_init(v.texture+a,b->low+a,seed);
        sd_oscillator_init(v.oscillator+a,b->low+a);
    }
    *out=v;return 1;
}
int drc_voice_set(DrcVoice *v,double amount) {
    if(!v||!v->bank||!unit(amount))return 0;v->target=amount;return 1;
}
int drc_voice_tick(DrcVoice *v,const SaVoice *dna,double phase,DrcFrame *f) {
    unsigned a,c;double w[SA_MAX_ANCHORS];const DrcBank *b;
    if(!v||!v->bank||!dna||dna->bank!=v->dna_bank||!f||!isfinite(phase)||phase<0||phase>=2*DRC_PI||
       !isfinite(dna->root_hz)||dna->root_hz<0||dna->root_hz>1000||!unit(dna->detail))return 0;
    b=v->bank;memset(f,0,sizeof *f);drc_weights(b,dna->root_hz,w);
    for(a=0;a<b->count;++a)if(b->has_low[a]) {
        double x[2],p=fmod(phase+dna->bank->offset[a],2*DRC_PI),weight=w[a]*drc_support(b,a,dna->root_hz);
        if(p<0)p+=2*DRC_PI;if(p>=2*DRC_PI)p=0;
        v->oscillator[a].phase=p;sd_texture_prepare(v->texture+a,b->low+a);
        sd_oscillator_sample(v->oscillator+a,v->texture+a,b->low+a,dna->detail,x);
        v->texture[a].fraction+=dna->root_hz/12000;
        f->support+=weight*weight;
        for(c=0;c<2;++c)f->raw[c]+=x[c]*b->scale[a]*weight;
    }
    v->amount+=v->follow*(v->target-v->amount);
    for(c=0;c<2;++c)f->output[c]=f->raw[c]*v->amount;
    ++v->frame;return 1;
}

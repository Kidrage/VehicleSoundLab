#include "oscillator.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
static float random_unit(uint64_t *seed) {
    uint64_t z=(*seed+=UINT64_C(0x9e3779b97f4a7c15));
    z=(z^(z>>30))*UINT64_C(0xbf58476d1ce4e5b9);z=(z^(z>>27))*UINT64_C(0x94d049bb133111eb);
    return (float)((z^(z>>31))>>11)*(1.0f/9007199254740992.0f);
}
void sr_cloud_init(SrCloud *s,const SrProfile *p,uint64_t seed) {
    unsigned b,j;memset(s,0,sizeof *s);
    for(b=0;b<p->bands;++b) {
        const SrBand *band=&p->band[b];
        float step=(band->high-band->low)/p->partials;
        float left=sqrtf(2*band->power[0]/p->partials),right=sqrtf(2*band->power[1]/p->partials);
        float independent=right*sqrtf(fmaxf(0,1-band->coherence[0]*band->coherence[0]-band->coherence[1]*band->coherence[1]));
        for(j=0;j<p->partials;++j) {
            SrOscillator *shared=&s->oscillator[s->count++],*other=&s->oscillator[s->count++];
            float phase;
            shared->hz=band->low+(j+.15f+.25f*random_unit(&seed))*step;
            other->hz=band->low+(j+.65f+.25f*random_unit(&seed))*step;
            phase=2*PI*random_unit(&seed);shared->re=cosf(phase);shared->im=sinf(phase);
            phase=2*PI*random_unit(&seed);other->re=cosf(phase);other->im=sinf(phase);
            shared->left=left;shared->right_re=right*band->coherence[0];shared->right_im=right*band->coherence[1];
            other->right_re=independent;
        }
    }
}
void sr_cloud_tune(SrCloud *s,float pitch) {
    unsigned i;for(i=0;i<s->count;++i) {
        SrOscillator *o=&s->oscillator[i];float phase=2*PI*o->hz*pitch/48000;
        o->cos_step=cosf(phase);o->sin_step=sinf(phase);
    }
}
void sr_cloud_tick(SrCloud *s,float out[2],int normalize) {
    unsigned i;out[0]=out[1]=0;
    for(i=0;i<s->count;++i) {
        SrOscillator *o=&s->oscillator[i];float next;
        if(normalize) { float unit=1/hypotf(o->re,o->im);o->re*=unit;o->im*=unit; }
        out[0]+=o->left*o->re;out[1]+=o->right_re*o->re-o->right_im*o->im;
        next=o->re*o->sin_step+o->im*o->cos_step;
        o->re=o->re*o->cos_step-o->im*o->sin_step;o->im=next;
    }
}
void sr_cloud_observe(SrCloud *s,unsigned bands,unsigned partials,float out[SR_MAX_BANDS][3],int normalize) {
    unsigned b,j;float scale=sqrtf(2.f/partials);
    for(b=0;b<bands;++b) {
        out[b][0]=out[b][1]=out[b][2]=0;
        for(j=0;j<2*partials;++j) {
            SrOscillator *o=&s->oscillator[2*b*partials+j];float next;
            if(normalize) { float unit=1/hypotf(o->re,o->im);o->re*=unit;o->im*=unit; }
            if(j%2)out[b][2]+=o->re;
            else {out[b][0]+=o->re;out[b][1]+=o->im;}
            next=o->re*o->sin_step+o->im*o->cos_step;
            o->re=o->re*o->cos_step-o->im*o->sin_step;o->im=next;
        }
        out[b][0]*=scale;out[b][1]*=scale;out[b][2]*=scale;
    }
}

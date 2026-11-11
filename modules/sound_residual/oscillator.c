#include "oscillator.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
static double random_unit(uint64_t *seed) {
    uint64_t z=(*seed+=UINT64_C(0x9e3779b97f4a7c15));
    z=(z^(z>>30))*UINT64_C(0xbf58476d1ce4e5b9);z=(z^(z>>27))*UINT64_C(0x94d049bb133111eb);
    return (double)((z^(z>>31))>>11)*(1.0/9007199254740992.0);
}
void sr_cloud_init(SrCloud *s,const SrProfile *p,uint64_t seed) {
    unsigned b,j;memset(s,0,sizeof *s);
    for(b=0;b<p->bands;++b) {
        const SrBand *band=&p->band[b];
        double step=(band->high-band->low)/p->partials;
        double left=sqrt(2*band->power[0]/p->partials),right=sqrt(2*band->power[1]/p->partials);
        double independent=right*sqrt(fmax(0,1-band->coherence[0]*band->coherence[0]-band->coherence[1]*band->coherence[1]));
        for(j=0;j<p->partials;++j) {
            SrOscillator *shared=&s->oscillator[s->count++],*other=&s->oscillator[s->count++];
            double phase;
            shared->hz=band->low+(j+.15+.25*random_unit(&seed))*step;
            other->hz=band->low+(j+.65+.25*random_unit(&seed))*step;
            phase=2*PI*random_unit(&seed);shared->re=cos(phase);shared->im=sin(phase);
            phase=2*PI*random_unit(&seed);other->re=cos(phase);other->im=sin(phase);
            shared->left=left;shared->right_re=right*band->coherence[0];shared->right_im=right*band->coherence[1];
            other->right_re=independent;
        }
    }
}
void sr_cloud_tune(SrCloud *s,double pitch) {
    unsigned i;for(i=0;i<s->count;++i) {
        SrOscillator *o=&s->oscillator[i];double phase=2*PI*o->hz*pitch/48000;
        o->cos_step=cos(phase);o->sin_step=sin(phase);
    }
}
void sr_cloud_tick(SrCloud *s,double out[2],int normalize) {
    unsigned i;out[0]=out[1]=0;
    for(i=0;i<s->count;++i) {
        SrOscillator *o=&s->oscillator[i];double next;
        if(normalize) { double unit=1/hypot(o->re,o->im);o->re*=unit;o->im*=unit; }
        out[0]+=o->left*o->re;out[1]+=o->right_re*o->re-o->right_im*o->im;
        next=o->re*o->sin_step+o->im*o->cos_step;
        o->re=o->re*o->cos_step-o->im*o->sin_step;o->im=next;
    }
}

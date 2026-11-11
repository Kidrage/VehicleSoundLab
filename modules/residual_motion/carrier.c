#include "carrier.h"
#include <math.h>
void rm_carrier_tick(SrCloud *s,unsigned partials,const double *gain,double raw[2],double shaped[2],int normalize) {
    unsigned i;raw[0]=raw[1]=shaped[0]=shaped[1]=0;
    for(i=0;i<s->count;++i) {
        SrOscillator *o=&s->oscillator[i];double next,left,right,g=gain[i/(2*partials)];
        if(normalize){double unit=1/hypot(o->re,o->im);o->re*=unit;o->im*=unit;}
        left=o->left*o->re;right=o->right_re*o->re-o->right_im*o->im;
        raw[0]+=left;raw[1]+=right;shaped[0]+=left*g;shaped[1]+=right*g;
        next=o->re*o->sin_step+o->im*o->cos_step;
        o->re=o->re*o->cos_step-o->im*o->sin_step;o->im=next;
    }
}

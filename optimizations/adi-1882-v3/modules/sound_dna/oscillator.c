#include "oscillator.h"
#include <math.h>
void sd_oscillator_init(SdOscillator *s,const SdProfile *m){unsigned h,c;s->phase=0;
    for(h=0;h<m->harmonics;++h)for(c=0;c<2;++c){float re=m->harmonic[h].mean[c*2],im=m->harmonic[h].mean[c*2+1],norm=hypotf(re,im);
        s->unit[h][c*2]=norm>1e-15f?re/norm:1;s->unit[h][c*2+1]=norm>1e-15f?im/norm:0;}}
void sd_oscillator_sample(SdOscillator *s,const SdTexture *t,const SdProfile *m,float amount,float out[2]){
    unsigned h,c;float base_c,base_s,cl,sl;out[0]=out[1]=0;base_c=cl=cosf(s->phase);base_s=sl=sinf(s->phase);
    for(h=0;h<m->harmonics;++h){const SdHarmonic *a=&m->harmonic[h];float next,z[4];
        for(c=0;c<4;++c)z[c]=a->mean[c]+amount*(t->left[h][c]+t->fraction*(t->right[h][c]-t->left[h][c]));
        for(c=0;c<2;++c){float re=s->unit[h][c*2],im=s->unit[h][c*2+1];
            out[c]+=hypotf(z[c*2],z[c*2+1])*(re*cl-im*sl);}
        next=sl*base_c+cl*base_s;cl=cl*base_c-sl*base_s;sl=next;
    }
}

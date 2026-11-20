#include "lookup.h"
#include <math.h>
void sx_position(const SaBank *b,float root,unsigned *lo,unsigned *hi,float *t) {
    *lo=*hi=0;*t=0;
    if(root>=b->profile[b->count-1]->base_hz)*lo=*hi=b->count-1;
    else if(root>b->profile[0]->base_hz) {
        while(*lo+1<b->count&&root>b->profile[*lo+1]->base_hz)++*lo;
        *hi=*lo+1;*t=(root-b->profile[*lo]->base_hz)/(b->profile[*hi]->base_hz-b->profile[*lo]->base_hz);
    }
}
float sx_phase(const SaBank *b,float root,unsigned h,unsigned c) {
    unsigned lo,hi;float t;sx_position(b,root,&lo,&hi,&t);
    return b->phase[lo][h][c]+(lo!=hi?t*b->delta[lo][h][c]:0);
}
static float mag(const SaBank *b,const SdTexture *texture,float detail,unsigned a,unsigned h,unsigned c) {
    const SdTexture *t=texture+a;const float *m=b->profile[a]->harmonic[h].mean;
    float re=m[2*c]+detail*(t->left[h][2*c]+t->fraction*(t->right[h][2*c]-t->left[h][2*c]));
    float im=m[2*c+1]+detail*(t->left[h][2*c+1]+t->fraction*(t->right[h][2*c+1]-t->left[h][2*c+1]));
    return hypotf(re,im);
}
float sx_magnitude(const SaBank *b,const SdTexture *texture,float detail,unsigned lo,unsigned hi,float t,unsigned h,unsigned c) {
    float m=mag(b,texture,detail,lo,h,c);
    if(lo!=hi)m+=t*(mag(b,texture,detail,hi,h,c)-m);
    return m;
}

#include "voice.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846

static int valid(double hz,double d,double g) {
    return isfinite(hz)&&hz>=0&&hz<=1000&&isfinite(d)&&d>=0&&d<=1&&isfinite(g)&&g>=0&&g<=1;
}
int sa_voice_init(SaVoice *v,const SaBank *b,uint64_t seed,double hz,double d,double g) {
    unsigned a;
    if (!v||!b||!b->count||b->count>SA_MAX_ANCHORS||!valid(hz,d,g)) return 0;
    memset(v,0,sizeof *v);v->bank=b;
    v->root_hz=v->root_target=hz;v->detail=v->detail_target=d;v->gain=v->gain_target=g;
    v->follow=1-exp(-1/(.018*48000));
    for (a=0;a<b->count;++a) sd_texture_init(&v->texture[a],b->profile[a],seed);
    return 1;
}
int sa_voice_set(SaVoice *v,double hz,double d,double g) {
    if (!v||!v->bank||!valid(hz,d,g)) return 0;
    v->root_target=hz;v->detail_target=d;v->gain_target=g;return 1;
}
static double magnitude(const SaVoice *v,unsigned a,unsigned h,unsigned c) {
    const SdTexture *t=&v->texture[a];
    const double *m=v->bank->profile[a]->harmonic[h].mean;
    double re=m[2*c]+v->detail*(t->left[h][2*c]+t->fraction*(t->right[h][2*c]-t->left[h][2*c]));
    double im=m[2*c+1]+v->detail*(t->left[h][2*c+1]+t->fraction*(t->right[h][2*c+1]-t->left[h][2*c+1]));
    return hypot(re,im);
}
void sa_voice_tick(SaVoice *v,double out[2]) {
    const SaBank *b=v->bank;
    unsigned a,h,c,lo=0,hi=0;
    double blend=0,cl=cos(v->phase),sl=sin(v->phase),base_c=cl,base_s=sl;
    v->root_hz+=v->follow*(v->root_target-v->root_hz);
    v->detail+=v->follow*(v->detail_target-v->detail);v->gain+=v->follow*(v->gain_target-v->gain);
    for (a=0;a<b->count;++a) sd_texture_prepare(&v->texture[a],b->profile[a]);
    /* Followers approach a boundary asymptotically; sub-nanohertz rounding
       must not label a stationary endpoint as uncovered forever. */
    v->coverage=v->root_hz<b->profile[0]->base_hz-1e-8?-1:v->root_hz>b->profile[b->count-1]->base_hz+1e-8?1:0;
    if (v->root_hz>=b->profile[b->count-1]->base_hz) lo=hi=b->count-1;
    else if (v->root_hz>b->profile[0]->base_hz) {
        while (lo+1<b->count && v->root_hz>b->profile[lo+1]->base_hz) ++lo;
        hi=lo+1;
        blend=(v->root_hz-b->profile[lo]->base_hz)/(b->profile[hi]->base_hz-b->profile[lo]->base_hz);
    }
    v->lower=lo;v->upper=hi;v->blend=blend;out[0]=out[1]=0;
    for (h=0;h<b->harmonics;++h) {
        double hz=(h+1)*v->root_hz, aa=1,next;
        /* Smoothly remove orders before Nyquist; pitch itself is never clamped
           to the training interval. Taper starts19.2k, reaches zero21.6kHz. */
        if (hz>=21600) break;
        if (hz>19200) { double x=(hz-19200)/2400;aa=1-x*x*(3-2*x); }
        for (c=0;c<2;++c) {
            double mag=magnitude(v,lo,h,c),re=b->unit[lo][h][2*c],im=b->unit[lo][h][2*c+1];
            if (lo!=hi) {
                double phase=b->phase[lo][h][c]+blend*b->delta[lo][h][c];
                mag+=blend*(magnitude(v,hi,h,c)-mag);
                if (blend==1) { re=b->unit[hi][h][2*c];im=b->unit[hi][h][2*c+1]; }
                else if (blend!=0) { re=sa_bank_sine(b,phase+PI/2);im=sa_bank_sine(b,phase); }
            }
            out[c]+=aa*mag*(re*cl-im*sl);
        }
        next=sl*base_c+cl*base_s;cl=cl*base_c-sl*base_s;sl=next;
    }
    out[0]*=v->gain;out[1]*=v->gain;
    v->phase+=2*PI*v->root_hz/48000;if (v->phase>=2*PI) v->phase-=2*PI;
    for (a=0;a<b->count;++a) v->texture[a].fraction+=v->root_hz/12000;
    ++v->frame;
}
void sa_voice_process(SaVoice *v,double *out,unsigned frames) {
    unsigned n;for (n=0;n<frames;++n) sa_voice_tick(v,out+2*n);
}

#include "source.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
static int valid(double pitch,double amount,double gain) {
    return isfinite(pitch)&&pitch>=.9&&pitch<=1.1&&isfinite(amount)&&amount>=0&&amount<=1&&isfinite(gain)&&gain>=0&&gain<=1;
}
static double uniform(SuSource *p) {
    uint64_t x=p->rng;x^=x>>12;x^=x<<25;x^=x>>27;p->rng=x;
    return (((x*UINT64_C(2685821657736338717))>>11)+.5)/9007199254740992.;
}
static double gaussian(SuSource *p) {
    double radius,angle;if(p->has_spare){p->has_spare=0;return p->spare;}
    radius=sqrt(-2*log(uniform(p)));angle=2*PI*uniform(p);p->spare=radius*sin(angle);p->has_spare=1;return radius*cos(angle);
}
static void coefficients(SuSource *p,double target[SU_HARMONICS][4]) {
    const SuModel *m=p->model;unsigned h,k,c,j;
    for(h=0;h<m->harmonics;++h){const SuHarmonic *a=&m->harmonic[h];
        for(c=0;c<4;++c){double x=0;
            for(k=0;k<m->components;++k)x+=a->basis[k][c]*p->pc[k]*sqrt(3/(2+m->rho[k]));
            for(j=0;j<4;++j)x+=a->root[c][j]*p->residual[h][j]*sqrt(3/(2+a->rho));
            target[h][c]=x;
        }
    }
}
static void advance(SuSource *p) {
    const SuModel *m=p->model;unsigned h,k,j;
    for(k=0;k<m->components;++k){double r=m->rho[k];p->pc[k]=r*p->pc[k]+sqrt(1-r*r)*gaussian(p);}
    for(h=0;h<m->harmonics;++h)for(j=0;j<4;++j){double r=m->harmonic[h].rho;
        p->residual[h][j]=r*p->residual[h][j]+sqrt(1-r*r)*gaussian(p);}
    ++p->updates;
}
int su_init(SuSource *p,const SuModel *m,uint64_t seed,double pitch,double amount,double gain) {
    unsigned h,k,j;if(!p||!m||!m->rate||!m->harmonics||m->harmonics>SU_HARMONICS||m->components>SU_COMPONENTS||
        m->window!=1024||m->hop!=256||!valid(pitch,amount,gain))return 0;
    memset(p,0,sizeof *p);p->model=m;p->rng=seed?seed:1;p->pitch=p->pitch_target=pitch;
    p->amount=p->amount_target=amount;p->gain=p->gain_target=gain;p->follow=1-exp(-1/(.018*m->rate));
    for(k=0;k<m->components;++k)p->pc[k]=gaussian(p);
    for(h=0;h<m->harmonics;++h)for(j=0;j<4;++j)p->residual[h][j]=gaussian(p);
    coefficients(p,p->left);advance(p);coefficients(p,p->right);return 1;
}
int su_set(SuSource *p,double pitch,double amount,double gain) {
    if(!p||!p->model||!valid(pitch,amount,gain))return 0;
    p->pitch_target=pitch;p->amount_target=amount;p->gain_target=gain;return 1;
}
void su_process(SuSource *p,double *stereo,unsigned frames) {
    const SuModel *m=p->model;unsigned n,h,c;
    for(n=0;n<frames;++n){double output[2]={0,0},cl,sl,base_c,base_s;
        while(p->fraction>=1){p->fraction-=1;memcpy(p->left,p->right,sizeof p->left);advance(p);coefficients(p,p->right);}
        p->pitch+=p->follow*(p->pitch_target-p->pitch);p->amount+=p->follow*(p->amount_target-p->amount);p->gain+=p->follow*(p->gain_target-p->gain);
        base_c=cl=cos(p->phase);base_s=sl=sin(p->phase);
        for(h=0;h<m->harmonics;++h){const SuHarmonic *a=&m->harmonic[h];double v[4],next;
            for(c=0;c<4;++c)v[c]=a->mean[c]+p->amount*(p->left[h][c]+p->fraction*(p->right[h][c]-p->left[h][c]));
            output[0]+=v[0]*cl-v[1]*sl;output[1]+=v[2]*cl-v[3]*sl;
            next=sl*base_c+cl*base_s;cl=cl*base_c-sl*base_s;sl=next;
        }
        stereo[2*n]=output[0]*p->gain;stereo[2*n+1]=output[1]*p->gain;
        p->phase+=2*PI*p->pitch/m->window;if(p->phase>=2*PI)p->phase-=2*PI;
        p->fraction+=p->pitch/m->hop;++p->frame;
    }
}

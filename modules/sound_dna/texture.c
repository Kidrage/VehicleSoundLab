#include "texture.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
static double uniform(SdTexture *p){uint64_t x=p->rng;x^=x>>12;x^=x<<25;x^=x>>27;p->rng=x;
    return (((x*UINT64_C(2685821657736338717))>>11)+.5)/9007199254740992.;}
static double gaussian(SdTexture *p){double r,a;if(p->has_spare){p->has_spare=0;return p->spare;}
    r=sqrt(-2*log(uniform(p)));a=2*PI*uniform(p);p->spare=r*sin(a);p->has_spare=1;return r*cos(a);}
static void coefficients(SdTexture *p,const SdProfile *m,double out[SD_MAX_HARMONICS][4]){
    unsigned h,c,k,j;for(h=0;h<m->harmonics;++h){const SdHarmonic *a=&m->harmonic[h];
        for(c=0;c<4;++c){double x=0;
            for(k=0;k<m->components;++k)x+=a->basis[k][c]*p->pc[k]*sqrt(3/(2+m->rho[k]));
            for(j=0;j<4;++j)x+=a->root[c][j]*p->residual[h][j]*sqrt(3/(2+a->rho));out[h][c]=x;}}
}
static void advance(SdTexture *p,const SdProfile *m){unsigned h,k,j;
    for(k=0;k<m->components;++k){double r=m->rho[k];p->pc[k]=r*p->pc[k]+sqrt(1-r*r)*gaussian(p);}
    for(h=0;h<m->harmonics;++h)for(j=0;j<4;++j){double r=m->harmonic[h].rho;p->residual[h][j]=r*p->residual[h][j]+sqrt(1-r*r)*gaussian(p);}++p->updates;
}
void sd_texture_init(SdTexture *p,const SdProfile *m,uint64_t seed){unsigned h,k,j;memset(p,0,sizeof *p);p->rng=seed?seed:1;
    for(k=0;k<m->components;++k)p->pc[k]=gaussian(p);
    for(h=0;h<m->harmonics;++h)for(j=0;j<4;++j)p->residual[h][j]=gaussian(p);
    coefficients(p,m,p->left);advance(p,m);coefficients(p,m,p->right);
}
void sd_texture_prepare(SdTexture *p,const SdProfile *m){while(p->fraction>=1){p->fraction-=1;memcpy(p->left,p->right,sizeof p->left);advance(p,m);coefficients(p,m,p->right);}}

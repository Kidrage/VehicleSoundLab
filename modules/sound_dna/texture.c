#include "texture.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
static double uniform(SdTexture *p){uint64_t x=p->rng;x^=x>>12;x^=x<<25;x^=x>>27;p->rng=x;
    return (((x*UINT64_C(2685821657736338717))>>11)+.5)/9007199254740992.;}
static double gaussian(SdTexture *p){double r,a;if(p->has_spare){p->has_spare=0;return p->spare;}
    r=sqrt(-2*log(uniform(p)));a=2*PI*uniform(p);p->spare=r*sin(a);p->has_spare=1;return r*cos(a);}
static void coefficients(SdTexture *p,const SdProfile *m,double out[SD_MAX_HARMONICS][4]){
    double common_scale[SD_MAX_COMPONENTS];
    unsigned h,c,k,j;
    /* Identical double values, reused across channels/harmonics. Keep the
       original multiplication/addition order and all RNG calls unchanged. */
    for(k=0;k<m->components;++k)common_scale[k]=sqrt(3/(2+m->rho[k]));
    for(h=0;h<m->harmonics;++h){const SdHarmonic *a=&m->harmonic[h];
        double residual_scale=sqrt(3/(2+a->rho));
        for(c=0;c<4;++c){double x=0;
            for(k=0;k<m->components;++k)x+=a->basis[k][c]*p->pc[k]*common_scale[k];
            for(j=0;j<4;++j)x+=a->root[c][j]*p->residual[h][j]*residual_scale;out[h][c]=x;}}
}
static void advance(SdTexture *p,const SdProfile *m){unsigned h,k,j;
    for(k=0;k<m->components;++k){double r=m->rho[k];p->pc[k]=r*p->pc[k]+sqrt(1-r*r)*gaussian(p);}
    for(h=0;h<m->harmonics;++h){double r=m->harmonic[h].rho,scale=sqrt(1-r*r);
        for(j=0;j<4;++j)p->residual[h][j]=r*p->residual[h][j]+scale*gaussian(p);}++p->updates;
}
void sd_texture_init(SdTexture *p,const SdProfile *m,uint64_t seed){unsigned h,k,j;memset(p,0,sizeof *p);p->rng=seed?seed:1;
    for(k=0;k<m->components;++k)p->pc[k]=gaussian(p);
    for(h=0;h<m->harmonics;++h)for(j=0;j<4;++j)p->residual[h][j]=gaussian(p);
    coefficients(p,m,p->left);advance(p,m);coefficients(p,m,p->right);
}
void sd_texture_prepare(SdTexture *p,const SdProfile *m){while(p->fraction>=1){p->fraction-=1;memcpy(p->left,p->right,sizeof p->left);advance(p,m);coefficients(p,m,p->right);}}

void sd_texture_prepare_batch(SdTexture *p,const SdProfile *const *m,unsigned count) {
    unsigned a,h,k,j;double scale[8];
    if(!count)return;
    for(a=0;a<count;++a)if(p[a].fraction>=1)break;
    if(a==count)return;
    /* A common source clock does not imply common random state. Check the
       actual innovation state before sharing work; never synchronize it. */
    for(a=1;a<count&&count<=8;++a)
        if(m[a]->harmonics!=m[0]->harmonics||m[a]->components!=m[0]->components||
           p[a].fraction!=p[0].fraction||p[a].rng!=p[0].rng||
           p[a].has_spare!=p[0].has_spare||memcmp(&p[a].spare,&p[0].spare,sizeof p[0].spare))break;
    if(a!=count) {for(a=0;a<count;++a)sd_texture_prepare(p+a,m[a]);return;}
    while(p[0].fraction>=1) {
        for(a=0;a<count;++a){p[a].fraction-=1;memcpy(p[a].left,p[a].right,sizeof p[a].left);}
        for(k=0;k<m[0]->components;++k) {
            double noise=gaussian(p);
            for(a=0;a<count;++a){double r=m[a]->rho[k];p[a].pc[k]=r*p[a].pc[k]+sqrt(1-r*r)*noise;}
        }
        for(h=0;h<m[0]->harmonics;++h) {
            for(a=0;a<count;++a){double r=m[a]->harmonic[h].rho;scale[a]=sqrt(1-r*r);}
            for(j=0;j<4;++j) {
                double noise=gaussian(p);
                for(a=0;a<count;++a) p[a].residual[h][j]=m[a]->harmonic[h].rho*p[a].residual[h][j]+scale[a]*noise;
            }
        }
        for(a=0;a<count;++a) {
            if(a){p[a].rng=p[0].rng;p[a].has_spare=p[0].has_spare;p[a].spare=p[0].spare;}
            ++p[a].updates;coefficients(p+a,m[a],p[a].right);
        }
    }
}

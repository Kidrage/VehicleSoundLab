#include "texture.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
static float uniform(SdTexture *p){uint64_t x=p->rng;x^=x>>12;x^=x<<25;x^=x>>27;p->rng=x;
    return (((x*UINT64_C(2685821657736338717))>>11)+.5f)/9007199254740992.f;}
static float gaussian(SdTexture *p){float r,a;if(p->has_spare){p->has_spare=0;return p->spare;}
    r=sqrtf(-2*logf(uniform(p)));a=2*PI*uniform(p);p->spare=r*sinf(a);p->has_spare=1;return r*cosf(a);}
static void coefficients(SdTexture *p,const SdProfile *m,float out[SD_MAX_HARMONICS][4]){
    unsigned h,c,k,j;
    /* Identical float values, reused across channels/harmonics. Keep the
       original multiplication/addition order and all RNG calls unchanged. */
    for(h=0;h<m->harmonics;++h){const SdHarmonic *a=&m->harmonic[h];
        float residual_scale=p->residual_scale[h];
        for(c=0;c<4;++c){float x=0;
            for(k=0;k<m->components;++k)x+=a->basis[k][c]*p->pc[k]*p->common_scale[k];
            for(j=0;j<4;++j)x+=a->root[c][j]*p->residual[h][j]*residual_scale;out[h][c]=x;}}
}
static void advance(SdTexture *p,const SdProfile *m){unsigned h,k,j;
    for(k=0;k<m->components;++k){float r=m->rho[k];p->pc[k]=r*p->pc[k]+p->pc_innovation[k]*gaussian(p);}
    for(h=0;h<m->harmonics;++h){float r=m->harmonic[h].rho,scale=p->residual_innovation[h];
        for(j=0;j<4;++j)p->residual[h][j]=r*p->residual[h][j]+scale*gaussian(p);}++p->updates;
}
void sd_texture_init(SdTexture *p,const SdProfile *m,uint64_t seed){unsigned h,k,j;memset(p,0,sizeof *p);p->rng=seed?seed:1;
    for(k=0;k<m->components;++k){float r=m->rho[k];p->common_scale[k]=sqrtf(3/(2+r));p->pc_innovation[k]=sqrtf(1-r*r);}
    for(h=0;h<m->harmonics;++h){float r=m->harmonic[h].rho;p->residual_scale[h]=sqrtf(3/(2+r));p->residual_innovation[h]=sqrtf(1-r*r);}
    for(k=0;k<m->components;++k)p->pc[k]=gaussian(p);
    for(h=0;h<m->harmonics;++h)for(j=0;j<4;++j)p->residual[h][j]=gaussian(p);
    coefficients(p,m,p->left);advance(p,m);coefficients(p,m,p->right);
}
void sd_texture_prepare(SdTexture *p,const SdProfile *m){while(p->fraction>=1){p->fraction-=1;memcpy(p->left,p->right,sizeof p->left);advance(p,m);coefficients(p,m,p->right);}}

void sd_texture_prepare_batch(SdTexture *p,const SdProfile *const *m,unsigned count) {
    unsigned a,h,k,j;float scale[8];
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
            float noise=gaussian(p);
            for(a=0;a<count;++a){float r=m[a]->rho[k];p[a].pc[k]=r*p[a].pc[k]+p[a].pc_innovation[k]*noise;}
        }
        for(h=0;h<m[0]->harmonics;++h) {
            for(a=0;a<count;++a)scale[a]=p[a].residual_innovation[h];
            for(j=0;j<4;++j) {
                float noise=gaussian(p);
                for(a=0;a<count;++a) p[a].residual[h][j]=m[a]->harmonic[h].rho*p[a].residual[h][j]+scale[a]*noise;
            }
        }
        for(a=0;a<count;++a) {
            if(a){p[a].rng=p[0].rng;p[a].has_spare=p[0].has_spare;p[a].spare=p[0].spare;}
            ++p[a].updates;coefficients(p+a,m[a],p[a].right);
        }
    }
}

#include "core/response_kernel.h"
#include "profiles/response_shape.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
void vsl_response_kernel_init(VslResponseKernel *k,const VslCharacterMode *m,unsigned count,float rate) {
    const VslResponseProfile *p=vsl_response_profile();unsigned i,j,a,b;
    memset(k,0,sizeof *k);if(count>VSL_RESPONSE_MAX_MODES)return;k->count=count;
    for(a=0;a<3;++a)for(i=0;i<count;++i)
        vsl_mode_init(&k->mode[a][i],m[i].hz,m[i].decay*p->decay_scale[a],rate);
    for(a=0;a<3;++a)for(b=0;b<3;++b)for(i=0;i<count;++i)for(j=0;j<count;++j) {
        float alpha=1/(m[i].decay*p->decay_scale[a])+1/(m[j].decay*p->decay_scale[b]);
        float difference=2*PI*(m[i].hz-m[j].hz),sum=2*PI*(m[i].hz+m[j].hz);
        /* Exact continuous inner product of two causal damped sinusoids. */
        if(k->mode[a][i].hz&&k->mode[b][j].hz)
            k->gram[a][b][i][j]=.5f*(alpha/(alpha*alpha+difference*difference)-alpha/(alpha*alpha+sum*sum));
    }
}
void vsl_response_kernel_advance(VslResponseKernel *k) {
    unsigned a,i;for(a=0;a<3;++a)for(i=0;i<k->count;++i)(void)vsl_mode_tick(&k->mode[a][i]);
}
void vsl_response_kernel_strike(VslResponseKernel *k,const float *w,float gain,float coordinate,float elapsed) {
    float blend[3]={0,1,0},base_energy=0,energy=0,normal=1;unsigned a,b,i,j;
    coordinate=fmaxf(-1,fminf(1,coordinate));
    if(coordinate!=0) {
        blend[1]=1-fabsf(coordinate);blend[coordinate>0?0:2]=fabsf(coordinate);
        for(i=0;i<k->count;++i)for(j=0;j<k->count;++j) {
            base_energy+=w[i]*w[j]*k->gram[1][1][i][j];
            for(a=0;a<3;++a)for(b=0;b<3;++b)
                energy+=blend[a]*blend[b]*w[i]*w[j]*k->gram[a][b][i][j];
        }
        if(energy>0&&base_energy>0)normal=sqrtf(base_energy/energy);
    }
    for(a=0;a<3;++a)if(blend[a]!=0)for(i=0;i<k->count;++i)
        vsl_mode_strike(&k->mode[a][i],gain*w[i]*blend[a]*normal,elapsed);
}
float vsl_response_kernel_read(const VslResponseKernel *k) {
    float x=0;unsigned a,i;for(a=0;a<3;++a)for(i=0;i<k->count;++i)x+=k->mode[a][i].real;return x;
}

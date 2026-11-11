#include "texture.h"
#include <stdio.h>
#include <string.h>
static SdProfile models[9];
static SdTexture serial[9],batch[9];
static int run(unsigned count,int difference) {
    const SdProfile *profiles[9];unsigned a,h,c,j,k,step;
    memset(models,0,sizeof models);
    for(a=0;a<count;++a) {
        SdProfile *m=models+a;profiles[a]=m;
        m->rate=48000;m->window=1024;m->hop=256;m->base_hz=20+10*a;
        m->harmonics=difference==2&&a==count-1?17:23;
        m->components=difference==1&&a==count-1?3:5;
        for(k=0;k<m->components;++k)m->rho[k]=(a%2?.9:-.9)+.005*k;
        for(h=0;h<m->harmonics;++h) {
            SdHarmonic *p=m->harmonic+h;p->rho=(h%2?.8:-.8)+.001*a;
            for(c=0;c<4;++c) {
                p->mean[c]=.01*(1+a+c)/(h+1);
                for(k=0;k<m->components;++k)p->basis[k][c]=.001*(1+a+k+c)/(h+1);
                for(j=0;j<4;++j)p->root[c][j]=.002*(1+c+j+a)/(h+1);
            }
        }
        sd_texture_init(serial+a,m,771+(difference==3&&a==count-1?9:0));
    }
    memcpy(batch,serial,sizeof serial);
    for(step=0;step<120;++step) {
        for(a=0;a<count;++a) {
            double increment=.017+.19*(step%13)+(difference==4?.01*a:0);
            serial[a].fraction+=increment;batch[a].fraction+=increment;
            sd_texture_prepare(serial+a,profiles[a]);
        }
        sd_texture_prepare_batch(batch,profiles,count);
        if(memcmp(serial,batch,count*sizeof *serial)) {
            fprintf(stderr,"batch state mismatch: count%u difference%d step%u\n",count,difference,step);
            return 0;
        }
    }
    return 1;
}
int main(void) {
    unsigned i;int difference;const unsigned counts[]={1,2,4,8,9};
    sd_texture_prepare_batch(NULL,NULL,0);
    for(i=0;i<sizeof counts/sizeof *counts;++i)for(difference=0;difference<5;++difference)
        if(!run(counts[i],difference))return 1;
    puts("PASS: batched texture entire state exact for1/2/4/8 anchors; >8/dimension/RNG/clock fallbacks exact");
    return 0;
}

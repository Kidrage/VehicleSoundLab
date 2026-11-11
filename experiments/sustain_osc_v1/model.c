#define _CRT_SECURE_NO_WARNINGS
#include "model.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static int real(FILE *f,double *v,double bound){return fscanf(f,"%lf",v)==1&&isfinite(*v)&&fabs(*v)<=bound;}
int su_model_load(const char *path,SuModel *model) {
    SuModel *m;FILE *f;char tag[32],tail[2];unsigned version,h,k,c,j;int ok=0;
    if(!path||!model)return 0;f=fopen(path,"rb");if(!f)return 0;m=calloc(1,sizeof *m);if(!m){fclose(f);return 0;}
    if(fscanf(f,"%31s %u %u %u %u %u %u",tag,&version,&m->rate,&m->window,&m->hop,&m->harmonics,&m->components)!=7||
       strcmp(tag,"VSL_SUSTAIN_OSC")||version!=1||m->rate<16000||m->rate>192000||m->window!=1024||m->hop!=256||
       !m->harmonics||m->harmonics>SU_HARMONICS||m->components>SU_COMPONENTS)goto done;
    for(k=0;k<m->components;++k)if(!real(f,&m->rho[k],.950000001))goto done;
    for(h=0;h<m->harmonics;++h){SuHarmonic *a=&m->harmonic[h];
        for(c=0;c<4;++c)if(!real(f,&a->mean[c],4))goto done;
        for(k=0;k<m->components;++k)for(c=0;c<4;++c)if(!real(f,&a->basis[k][c],4))goto done;
        if(!real(f,&a->rho,.950000001))goto done;
        for(c=0;c<4;++c)for(j=0;j<4;++j)if(!real(f,&a->root[c][j],4))goto done;
    }
    if(fscanf(f,"%1s",tail)==1||ferror(f))goto done;
    *model=*m;ok=1;
done:free(m);fclose(f);return ok;
}

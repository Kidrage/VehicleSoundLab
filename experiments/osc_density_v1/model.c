#define _CRT_SECURE_NO_WARNINGS
#include "model.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
void do_model_free(DoModel *m) {
    unsigned i;if(!m)return;
    if(m->grains)for(i=0;i<m->count;++i)free(m->grains[i].tones);
    free(m->grains);memset(m,0,sizeof *m);
}
int do_model_load(const char *path,DoModel *model) {
    DoModel m={0};FILE *f;char tag[32],tail[2];unsigned version,i,j;int ok=0;
    if(!path||!model)return 0;f=fopen(path,"rb");if(!f)return 0;
    if(fscanf(f,"%31s %u %u %u %u %u %u",tag,&version,&m.rate,&m.frames,&m.window,&m.hop,&m.count)!=7||
       strcmp(tag,"VSL_DENSE_OSC")||version!=1||m.rate<16000||m.rate>192000||
       !m.frames||m.frames>m.rate*60||m.window<64||m.window>1024||m.window%4||
       m.hop!=m.window/4||!m.count||m.count>20000)goto done;
    m.grains=calloc(m.count,sizeof *m.grains);if(!m.grains){m.count=0;goto done;}
    for(i=0;i<m.count;++i) {
        DoGrain *g=&m.grains[i];
        if(fscanf(f,"%d %u",&g->start,&g->count)!=2||!g->count||g->count>m.window/2+1||
           g->start!=-(int)m.window+(int)m.hop+(int)(i*m.hop)||g->start>=(int)m.frames)goto done;
        g->tones=calloc(g->count,sizeof *g->tones);if(!g->tones)goto done;
        for(j=0;j<g->count;++j) {
            DoTone *t=&g->tones[j];
            if(fscanf(f,"%u %lf %lf",&t->bin,&t->real,&t->imag)!=3||t->bin>m.window/2||
               (j&&t->bin<=g->tones[j-1].bin)||!isfinite(t->real)||!isfinite(t->imag)||
               fabs(t->real)>1e4||fabs(t->imag)>1e4)goto done;
        }
    }
    if(m.grains[m.count-1].start+(int)m.hop<(int)m.frames||fscanf(f,"%1s",tail)==1||ferror(f))goto done;
    do_model_free(model);*model=m;memset(&m,0,sizeof m);ok=1;
done:do_model_free(&m);fclose(f);return ok;
}

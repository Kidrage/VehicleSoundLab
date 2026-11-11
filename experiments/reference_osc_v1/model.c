#define _CRT_SECURE_NO_WARNINGS
#include "model.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <inttypes.h>
static int real(FILE *f,double *v) { return fscanf(f,"%lf",v)==1&&isfinite(*v); }
void ro_model_free(RoModel *m) {
    unsigned i;if(!m)return;
    if(m->segments)for(i=0;i<m->count;++i)free(m->segments[i].partials);
    free(m->segments);memset(m,0,sizeof *m);
}
int ro_model_load(const char *path,RoModel *model) {
    FILE *f;RoModel m={0};char tag[32],tail[2];unsigned version,i,j,c;int ok=0;
    if(!path||!model)return 0;
    f=fopen(path,"rb");
    if(!f)return 0;
    if(fscanf(f,"%31s %u %u %" SCNu64 " %u",tag,&version,&m.rate,&m.frames,&m.count)!=5||
       strcmp(tag,"VSL_REFERENCE_OSC")||version!=1||m.rate<16000||m.rate>192000||
       !m.frames||m.frames>(uint64_t)m.rate*60||!m.count||m.count>RO_MAX_SEGMENTS)goto done;
    m.segments=calloc(m.count,sizeof *m.segments);if(!m.segments) { m.count=0;goto done; }
    for(i=0;i<m.count;++i) {
        RoSegment *s=&m.segments[i];
        if(fscanf(f,"%" SCNu64 " %u %u",&s->start,&s->frames,&s->count)!=3||
           !s->frames||s->frames>m.rate||s->start>=m.frames||s->frames>m.frames-s->start||s->count>RO_MAX_ROWS||
           (i&&s->start<m.segments[i-1].start+m.segments[i-1].frames))goto done;
        if(!s->count)continue;
        s->partials=calloc(s->count,sizeof *s->partials);if(!s->partials)goto done;
        for(j=0;j<s->count;++j) {
            RoPartial *p=&s->partials[j];
            if(fscanf(f,"%u",&p->group)!=1||p->group>1)goto done;
            for(c=0;c<2;++c) {
                RoChannel *a=&p->channel[c];
                if(!real(f,&a->amplitude0)||!real(f,&a->amplitude1)||!real(f,&a->phase0)||!real(f,&a->omega0)||!real(f,&a->c2)||!real(f,&a->c3)||
                   a->amplitude0<0||a->amplitude1<0||a->amplitude0>16||a->amplitude1>16||fabs(a->phase0)>1e12||fabs(a->omega0)>2*3.14159265358979323846*m.rate||fabs(a->c2)>1e13||fabs(a->c3)>1e16)goto done;
            }
        }
    }
    if(fscanf(f,"%1s",tail)==1||ferror(f))goto done;
    ro_model_free(model);*model=m;memset(&m,0,sizeof m);ok=1;
done:ro_model_free(&m);fclose(f);return ok;
}

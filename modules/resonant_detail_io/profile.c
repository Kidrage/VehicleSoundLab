#define _CRT_SECURE_NO_WARNINGS
#include "profile.h"
#include "io/file.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static int number(FILE *f,double *v) {return fscanf(f,"%lf",v)==1&&isfinite(*v);}
int rdt_profile_read(FILE *f,RdtProfile *out) {
    RdtProfile p={0};char tag[32],extra;unsigned version,b,j,s;int ok=0;
    if(!f||!out)return 0;
    if(fscanf(f,"%31s %u %u %u %u %lf",tag,&version,&p.rate,&p.count,&p.warmup_frames,&p.base_hz)!=6||
       strcmp(tag,"VSL_RESONANT_DETAIL")||version!=1||!p.count||p.count>RDT_MAX_BANDS)goto done;
    for(b=0;b<p.count;++b) {
        RdtBand *m=p.band+b;
        if(fscanf(f,"%u %u %u",&m->order,&m->sections,&m->envelope_order)!=3||
           !m->order||m->order>RDT_MAX_AR||!m->sections||m->sections>RDT_MAX_SOS||m->envelope_order>RDT_MAX_ENVELOPE)goto done;
        if(!number(f,&m->low_hz)||!number(f,&m->high_hz)||!number(f,&m->sigma)||
           !number(f,&m->gain)||!number(f,&m->right_over_left))goto done;
        for(j=0;j<=m->order;++j)if(!number(f,&m->a[j]))goto done;
        for(s=0;s<m->sections;++s)for(j=0;j<6;++j)if(!number(f,&m->sos[s][j]))goto done;
        for(j=0;j<2*m->envelope_order;++j)if(!number(f,&m->beta[j]))goto done;
    }
    if(fscanf(f," %c",&extra)==1||ferror(f)||!rdt_profile_valid(&p))goto done;
    *out=p;ok=1;
done:return ok;
}
int rdt_profile_load(const char *path,RdtProfile *out) {
    FILE *f;int ok;
    if(!path||!out||!(f=vsl_fopen(path,"rb")))return 0;
    ok=rdt_profile_read(f,out);fclose(f);return ok;
}

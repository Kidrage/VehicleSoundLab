#define _CRT_SECURE_NO_WARNINGS
#include "profile.h"
#include "io/file.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
int rvs_profile_load(const char *path,RvsProfile *out) {
    FILE *f=NULL;RvsProfile *p=NULL;char tag[40],extra;unsigned version,i,j,k,c,n;int ok=0;
    if(!path||!out||!(f=vsl_fopen(path,"rb"))||!(p=calloc(1,sizeof *p)))goto done;
    if(fscanf(f,"%39s %u %u %u %u %lf",tag,&version,&p->rate,&p->count,&p->warmup_frames,&p->base_hz)!=6||
       strcmp(tag,"VSL_STEREO_RESONANCE")||version!=1||!p->count||p->count>RVS_MAX_BANDS)goto done;
    for(i=0;i<p->count;++i) {
        RvsBand *b=p->band+i;
        if(fscanf(f,"%u %u %lf %lf %lf",&b->order,&b->post.sections,&b->low_hz,&b->high_hz,&b->gain)!=5||
           !b->order||b->order>RVS_MAX_ORDER||!b->post.sections||b->post.sections>RDT_MAX_SOS)goto done;
        for(j=0;j<b->order;++j)for(k=0;k<2;++k)for(c=0;c<2;++c)if(fscanf(f,"%lf",&b->a[j][k][c])!=1)goto done;
        for(j=0;j<2;++j)for(k=0;k<2;++k)if(fscanf(f,"%lf",&b->noise[j][k])!=1)goto done;
        for(j=0;j<b->post.sections;++j)for(k=0;k<6;++k)if(fscanf(f,"%lf",&b->post.sos[j][k])!=1)goto done;
        n=2*b->order;
        for(j=0;j<n;++j)for(k=0;k<n;++k)if(fscanf(f,"%lf",&b->certificate[j][k])!=1)goto done;
    }
    if(fscanf(f," %c",&extra)==1||ferror(f)||!rvs_profile_valid(p))goto done;
    *out=*p;ok=1;
done:if(f)fclose(f);free(p);return ok;
}

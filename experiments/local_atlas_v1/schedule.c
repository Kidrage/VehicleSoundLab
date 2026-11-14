#define _CRT_SECURE_NO_WARNINGS
#include "schedule.h"
#include "input.h"
#include "io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int la_schedule_load(LaSchedule *out,const char *path) {
    FILE *f=NULL;LaSchedule *t=NULL;char tag[64],tail[2];unsigned version,i;int ok=0;
    if(!out||!path||!(f=vsl_fopen(path,"rb"))||!(t=calloc(1,sizeof *t)))goto done;
    if(fscanf(f,"%63s",tag)!=1||strcmp(tag,"VSL_LOCAL_ATLAS_TRACE")||
       !la_unsigned(f,1,&version)||version!=1||!la_unsigned(f,2880000,&t->frames)||!t->frames||
       !la_unsigned(f,LA_MAX_EVENTS,&t->count)||!t->count)goto done;
    for(i=0;i<t->count;++i) {
        LaEvent *e=t->event+i;
        if(!la_unsigned(f,t->frames-1,&e->frame)||fscanf(f,"%lf %lf %lf",&e->root_hz,&e->detail,&e->gain)!=3||
           (!i&&e->frame)||e->frame>=t->frames||(i&&e->frame<=t->event[i-1].frame)||
           !isfinite(e->root_hz)||e->root_hz<0||e->root_hz>1000||
           !isfinite(e->detail)||e->detail<0||e->detail>1||
           !isfinite(e->gain)||e->gain<0||e->gain>1)goto done;
    }
    if(fscanf(f,"%1s",tail)==1||ferror(f))goto done;
    *out=*t;ok=1;
done:if(f)fclose(f);free(t);return ok;
}

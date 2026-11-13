#define _CRT_SECURE_NO_WARNINGS
#include "io.h"
#include "io/file.h"
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
static int integer(FILE *file,unsigned *out) {
    char token[32],*end;unsigned long value;unsigned k;
    if(fscanf(file,"%31s",token)!=1)return 0;
    for(k=0;token[k];++k)if(!isdigit((unsigned char)token[k]))return 0;
    errno=0;value=strtoul(token,&end,10);
    if(errno||*end||value>UINT_MAX)return 0;
    *out=(unsigned)value;return 1;
}
int ms_profile_read(FILE *file,MsProfile *out) {
    MsProfile p;char tag[32];unsigned version,k;int ch;
    if(!file||!out)return 0;
    memset(&p,0,sizeof p);
    if(fscanf(file,"%31s",tag)!=1||strcmp(tag,"VSL_MODAL_SOURCE")||
       !integer(file,&version)||!integer(file,&p.rate)||!integer(file,&p.count)||
       version!=1||!p.count||p.count>MS_MAX_MODES)return 0;
    for(k=0;k<p.count;++k) {
        MsMode *m=p.mode+k;
        if(fscanf(file,"%lf %lf %lf %lf %lf",&m->hz,m->amplitude,m->amplitude+1,m->phase,m->phase+1)!=5)return 0;
    }
    do{ch=fgetc(file);}while(ch!=EOF&&isspace((unsigned char)ch));
    if(ch!=EOF||ferror(file)||!ms_profile_valid(&p))return 0;
    *out=p;return 1;
}
int ms_profile_load(const char *path,MsProfile *out) {
    FILE *f;MsProfile p;int ok;
    if(!path||!out||(f=vsl_fopen(path,"rb"))==NULL)return 0;
    ok=ms_profile_read(f,&p);if(fclose(f))ok=0;
    if(ok)*out=p;return ok;
}

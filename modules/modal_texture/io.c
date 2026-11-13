#define _CRT_SECURE_NO_WARNINGS
#include "io.h"
#include "io/file.h"
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
static int integer(FILE *f,unsigned *out) {
    char token[32],*end;unsigned long value;unsigned i;
    if(fscanf(f,"%31s",token)!=1)return 0;
    for(i=0;token[i];++i)if(!isdigit((unsigned char)token[i]))return 0;
    errno=0;value=strtoul(token,&end,10);
    if(errno||*end||value>UINT_MAX)return 0;*out=(unsigned)value;return 1;
}
int mt_profile_read(FILE *f,MtProfile *out) {
    MtProfile p;char tag[32];unsigned version,i,j;int ch;
    if(!f||!out)return 0;memset(&p,0,sizeof p);
    if(fscanf(f,"%31s",tag)!=1||strcmp(tag,"VSL_MODAL_TEXTURE")||!integer(f,&version)||version!=1||
       !integer(f,&p.rate)||!integer(f,&p.count)||!p.count||p.count>MT_MAX_MODES||
       !integer(f,&p.hop_frames)||fscanf(f,"%lf",&p.alpha)!=1)return 0;
    for(i=0;i<p.count;++i)for(j=0;j<p.count;++j)if(fscanf(f,"%lf",&p.factor[i][j])!=1)return 0;
    do{ch=fgetc(f);}while(ch!=EOF&&isspace((unsigned char)ch));
    if(ch!=EOF||ferror(f)||!mt_profile_valid(&p))return 0;*out=p;return 1;
}
int mt_profile_load(const char *path,MtProfile *out) {
    FILE *f;MtProfile p;int ok;
    if(!path||!out||(f=vsl_fopen(path,"rb"))==NULL)return 0;
    ok=mt_profile_read(f,&p);if(fclose(f))ok=0;if(ok)*out=p;return ok;
}

#define _CRT_SECURE_NO_WARNINGS
#include "assets.h"
#include "input.h"
#include "io/file.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int la_assets_load(LaAssets *out,const char *path) {
    FILE *f=NULL;LaAssets *t=NULL;const SdProfile *p[SA_MAX_ANCHORS];
    char tag[64],tail[2];unsigned version,count,i;int ch,ok=0;
    if(!out||!path||!(f=vsl_fopen(path,"rb"))||!(t=calloc(1,sizeof *t)))goto done;
    if(fscanf(f,"%63s",tag)!=1||strcmp(tag,"VSL_LOCAL_ATLAS")||
       !la_unsigned(f,1,&version)||version!=1||!la_unsigned(f,SA_MAX_ANCHORS,&count)||!count||
       !la_unsigned(f,32,&t->align_orders))goto done;
    while((ch=fgetc(f))!='\n')if(ch==EOF||(ch!=' '&&ch!='\r'&&ch!='\t'))goto done;
    for(i=0;i<count;++i) {
        size_t n;
        if(!fgets(t->paths[i],sizeof t->paths[i],f))goto done;
        n=strcspn(t->paths[i],"\r\n");
        if(!n||n==sizeof t->paths[i]-1)goto done;
        t->paths[i][n]=0;
        if(!sd_profile_load_bandlimited(t->paths[i],t->models+i))goto done;p[i]=t->models+i;
    }
    if(fscanf(f,"%1s",tail)==1||ferror(f)||!sa_bank_init_bandlimited(&t->bank,p,count,t->align_orders))goto done;
    *out=*t;
    for(i=0;i<count;++i)out->bank.profile[i]=out->models+i;
    ok=1;
done:if(f)fclose(f);free(t);return ok;
}

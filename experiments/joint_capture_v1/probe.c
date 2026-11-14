#define _CRT_SECURE_NO_WARNINGS
#include "session.h"
#include "atlas_take_io/file.h"
#include "io/file.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif
static int integer(const char *s,uint64_t *v) {
    const char *p=s;char *end;if(!*p)return 0;
    while(*p){if(*p<'0'||*p>'9')return 0;++p;}
    errno=0;*v=strtoull(s,&end,10);return !errno&&!*end;
}
static int run(int argc,char **argv) {
    AtTake t={0};uint64_t a,b;int ok=0;
    if(argc==2&&!strcmp(argv[1],"--describe")){puts("vsl.joint-capture/2");return 0;}
    if(argc==5&&!strcmp(argv[1],"make")) {
        FILE *existing;
        if(!integer(argv[2],&a)||a>11||!integer(argv[3],&b)||!b)return 2;
        existing=vsl_fopen(argv[4],"rb");if(existing){fclose(existing);return 3;}
        ok=jc_record((int)a,b,&t)&&at_take_save(&t,argv[4]);
    }else if(argc==6&&!strcmp(argv[1],"export")) {
        if(!integer(argv[4],&a)||!a||a>512||!integer(argv[5],&b)||(b!=2&&b!=12))return 2;
        ok=at_take_load(&t,argv[2])&&jc_export(&t,argv[3],(unsigned)a,(int)b);
    }else return 2;
    at_take_free(&t);return ok?0:4;
}
#ifdef _WIN32
int wmain(int argc,wchar_t **wide) {
    char **args=calloc((size_t)argc,sizeof *args);int result=2,i;if(!args)return 2;
    for(i=0;i<argc;++i){int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        if(!n||!(args[i]=malloc((size_t)n))||!WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],n,NULL,NULL))goto done;}
    result=run(argc,args);
done:for(i=0;i<argc;++i)free(args[i]);free(args);return result;
}
#else
int main(int argc,char **argv){return run(argc,argv);}
#endif

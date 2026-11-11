#define _CRT_SECURE_NO_WARNINGS
#include "profile.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>
#ifdef _WIN32
#include <windows.h>
#endif
static FILE *open_utf8(const char *path){
#ifdef _WIN32
    FILE *f=NULL;int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,NULL,0);wchar_t *wide;
    if(!n||!(wide=malloc((size_t)n*sizeof *wide)))return NULL;
    if(MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,wide,n))f=_wfopen(wide,L"rb");free(wide);return f;
#else
    return fopen(path,"rb");
#endif
}
int lr_profile_valid(const LrProfile *m){unsigned i;double sum=0;
    if(!m||m->rate!=48000||m->count<16||m->count>LR_MAX_OSCILLATORS||!isfinite(m->first_hz)||m->first_hz<25||
       !isfinite(m->step_hz)||m->step_hz<.5||m->step_hz>10||
       (m->first_hz+(m->count-1)*m->step_hz)*1.1>450||!isfinite(m->tau)||m->tau<.02||m->tau>.15)return 0;
    for(i=0;i<m->count;++i){double a=m->amplitude[i];if(!isfinite(a)||a<0||a>.1)return 0;sum+=a*a;}
    return sum>1e-10&&sum<=.09;
}
int lr_profile_load(const char *path,LrProfile *profile){FILE *f;LrProfile m={0};unsigned version,i;char tag[32],tail;int ok=0;
    if(!path||!profile||!(f=open_utf8(path)))return 0;
    if(fscanf(f,"%31s %u %u %u %lf %lf %lf",tag,&version,&m.rate,&m.count,&m.first_hz,&m.step_hz,&m.tau)!=7||
       strcmp(tag,"VSL_LOW_RUMBLE")||version!=2||m.count>LR_MAX_OSCILLATORS)goto done;
    for(i=0;i<m.count;++i)if(fscanf(f,"%lf",&m.amplitude[i])!=1)goto done;
    if(!lr_profile_valid(&m)||fscanf(f," %c",&tail)==1||ferror(f))goto done;
    *profile=m;ok=1;
done:fclose(f);return ok;
}

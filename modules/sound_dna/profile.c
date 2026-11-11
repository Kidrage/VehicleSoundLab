#define _CRT_SECURE_NO_WARNINGS
#include "profile.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
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
static int real(FILE *f,double *v,double bound){return fscanf(f,"%lf",v)==1&&isfinite(*v)&&fabs(*v)<=bound;}
int sd_profile_load(const char *path,SdProfile *profile){
    FILE *f;SdProfile *m;char tag[32],tail;unsigned version,h,k,c,j;int ok=0;
    if(!path||!profile||!(f=open_utf8(path)))return 0;
    m=calloc(1,sizeof *m);if(!m){fclose(f);return 0;}
    if(fscanf(f,"%31s %u %u %u %u %u %u",tag,&version,&m->rate,&m->window,&m->hop,&m->harmonics,&m->components)!=7||
        (strcmp(tag,"VSL_SUSTAIN_OSC")&&strcmp(tag,"VSL_SOUND_DNA"))||version!=1||m->rate!=48000||m->window!=1024||m->hop!=256||
        !m->harmonics||m->harmonics>SD_MAX_HARMONICS||m->components>SD_MAX_COMPONENTS)goto done;
    m->base_hz=m->rate/(double)m->window;
    if(!strcmp(tag,"VSL_SOUND_DNA")&&!real(f,&m->base_hz,2000))goto done;
    if(m->base_hz<5||m->harmonics*m->base_hz*1.1>.45*m->rate)goto done;
    for(k=0;k<m->components;++k)if(!real(f,&m->rho[k],.95))goto done;
    for(h=0;h<m->harmonics;++h){SdHarmonic *a=&m->harmonic[h];
        for(c=0;c<4;++c)if(!real(f,&a->mean[c],4))goto done;
        for(k=0;k<m->components;++k)for(c=0;c<4;++c)if(!real(f,&a->basis[k][c],4))goto done;
        if(!real(f,&a->rho,.95))goto done;
        for(c=0;c<4;++c)for(j=0;j<4;++j)if(!real(f,&a->root[c][j],4))goto done;
    }
    if(fscanf(f," %c",&tail)==1||ferror(f))goto done;*profile=*m;ok=1;
done:free(m);fclose(f);return ok;
}

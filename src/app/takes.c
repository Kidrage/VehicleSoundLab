#define _CRT_SECURE_NO_WARNINGS
#include "takes.h"
#include "io/take_file.h"
#include <stdio.h>
static int utf8(const wchar_t *path,char *out,unsigned n) { return WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,path,-1,out,n,NULL,NULL)>0; }
void vsl_takes_free(VslTakes *t) { vsl_take_free(&t->take); }
int vsl_takes_save(VslTakes *t,const wchar_t *path) {
    char p[MAX_PATH*4];if(!utf8(path,p,sizeof p)||!vsl_take_save(p,&t->take))return 0;
    t->saved=1;wcscpy(t->path,path);return 1;
}
int vsl_takes_preserve(VslTakes *t,const wchar_t *workspace) {
    wchar_t dir[MAX_PATH],path[MAX_PATH];SYSTEMTIME now;unsigned i;
    if(t->saved||!t->take.frames)return 1;
    swprintf(dir,MAX_PATH,L"%s\\performances",workspace);
    if(!CreateDirectoryW(dir,NULL)&&GetLastError()!=ERROR_ALREADY_EXISTS)return 0;
    GetLocalTime(&now);
    for(i=0;i<100;++i) {
        swprintf(path,MAX_PATH,L"%s\\take_%04u%02u%02u_%02u%02u%02u_%03u_%02u.vsltake",dir,now.wYear,now.wMonth,now.wDay,now.wHour,now.wMinute,now.wSecond,now.wMilliseconds,i);
        if(GetFileAttributesW(path)==INVALID_FILE_ATTRIBUTES)return vsl_takes_save(t,path);
    }
    return 0;
}
int vsl_takes_new(VslTakes *t,VslAudio *a) {
    VslTake next={0};
    if(a->thread||!vsl_take_allocate(&next,VSL_TAKE_EVENTS))return 0;
    if(!vsl_take_begin(&next,a->engine)) { vsl_take_free(&next);return 0; }
    vsl_take_free(&t->take);t->take=next;t->saved=0;t->path[0]=0;
    a->take=&t->take;a->take_mode=1;return 1;
}
int vsl_takes_play(VslTakes *t,VslAudio *a,const wchar_t *path) {
    char p[MAX_PATH*4];VslTake next={0};
    if(a->thread||!utf8(path,p,sizeof p)||!vsl_take_load(p,&next))return 0;
    if(!vsl_take_player_init(&a->player,a->engine,&next)) { vsl_take_free(&next);return 0; }
    vsl_take_free(&t->take);t->take=next;t->saved=1;wcscpy(t->path,path);
    a->take=&t->take;a->player.take=&t->take;a->take_mode=2;return 1;
}

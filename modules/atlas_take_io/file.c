#define _CRT_SECURE_NO_WARNINGS
#include "file.h"
#include "io/file.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#ifdef _WIN32
#include <windows.h>
#include <io.h>
#else
#include <unistd.h>
#endif
int at_take_load(AtTake *t,const char *path) {
    FILE *f;long size;unsigned char *data=NULL;int ok=0;
    if(!t||!path||!(f=vsl_fopen(path,"rb")))return 0;
    if(fseek(f,0,SEEK_END)||(size=ftell(f))<0||(unsigned long)size>AT_FILE_LIMIT||fseek(f,0,SEEK_SET))goto done;
    data=malloc((size_t)size);if(!data)goto done;
    if(fread(data,1,(size_t)size,f)!=(size_t)size||ferror(f))goto done;
    ok=at_take_decode(t,data,(size_t)size);
done:free(data);fclose(f);return ok;
}
int at_take_save(const AtTake *t,const char *path) {
    unsigned char *data=NULL;size_t size=0;int ok=0;FILE *f=NULL;
#ifdef _WIN32
    wchar_t *wide=NULL,*temporary=NULL;int n;unsigned attempt;HANDLE handle=INVALID_HANDLE_VALUE;
    if(!path||!at_take_encode(t,&data,&size))return 0;
    n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,NULL,0);
    if(!n||n>32000)goto done;
    wide=calloc((size_t)n,sizeof *wide);temporary=calloc((size_t)n+80,sizeof *temporary);
    if(!wide||!temporary||!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,wide,n))goto done;
    for(attempt=0;attempt<100;++attempt) {
        swprintf(temporary,(size_t)n+80,L"%ls.tmp-%lu-%llu-%u",wide,GetCurrentProcessId(),GetTickCount64(),attempt);
        handle=CreateFileW(temporary,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
        if(handle!=INVALID_HANDLE_VALUE)break;
        if(GetLastError()!=ERROR_FILE_EXISTS)goto done;
    }
    if(handle==INVALID_HANDLE_VALUE)goto done;
    {int descriptor=_open_osfhandle((intptr_t)handle,_O_BINARY);
        if(descriptor<0){CloseHandle(handle);DeleteFileW(temporary);goto done;}
        f=_fdopen(descriptor,"wb");if(!f){_close(descriptor);DeleteFileW(temporary);goto done;}}
    ok=fwrite(data,1,size,f)==size&&!ferror(f)&&!fflush(f)&&!_commit(_fileno(f));
    if(fclose(f))ok=0;f=NULL;
    if(ok)ok=MoveFileExW(temporary,wide,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=0;
    if(!ok)DeleteFileW(temporary);
done:free(wide);free(temporary);
#else
    char *temporary=NULL;int descriptor;
    if(!path||!at_take_encode(t,&data,&size))return 0;
    temporary=malloc(strlen(path)+16);if(!temporary)goto done;
    sprintf(temporary,"%s.tmp-XXXXXX",path);descriptor=mkstemp(temporary);if(descriptor<0)goto done;
    f=fdopen(descriptor,"wb");if(!f){close(descriptor);unlink(temporary);goto done;}
    ok=fwrite(data,1,size,f)==size&&!ferror(f)&&!fflush(f)&&!fsync(fileno(f));
    if(fclose(f))ok=0;f=NULL;if(ok)ok=rename(temporary,path)==0;if(!ok)unlink(temporary);
done:free(temporary);
#endif
    free(data);return ok;
}

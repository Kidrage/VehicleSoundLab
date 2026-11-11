#define _CRT_SECURE_NO_WARNINGS
#include "file.h"
#ifdef _WIN32
#include <windows.h>
FILE *vsl_fopen(const char *path,const char *mode) {
    wchar_t wide[32768],wm[16];
    if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,wide,32768) ||
       !MultiByteToWideChar(CP_UTF8,0,mode,-1,wm,16))return NULL;
    return _wfopen(wide,wm);
}
#else
FILE *vsl_fopen(const char*path,const char*mode) { return fopen(path,mode); }
#endif

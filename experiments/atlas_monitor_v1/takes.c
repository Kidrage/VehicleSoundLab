#define _CRT_SECURE_NO_WARNINGS
#include "takes.h"
#include "atlas_take_io/file.h"
#include <commdlg.h>
#include <stdio.h>
static int unsaved;
static int utf8(const wchar_t *path,char *out,int capacity) {return WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,path,-1,out,capacity,NULL,NULL)!=0;}
int am_take_preserve(HWND owner,AmAudio *a) {
    wchar_t path[4096];char encoded[16384];SYSTEMTIME time;
    am_audio_stop(a);
    if(!unsaved||!a->ready){unsaved=0;return 1;}
    CreateDirectoryW(L"performances",NULL);CreateDirectoryW(L"performances/atlas",NULL);GetLocalTime(&time);
    swprintf(path,4096,L"performances/atlas/%04u%02u%02u-%02u%02u%02u-%03u-%lu-%llu.vslrun",
        time.wYear,time.wMonth,time.wDay,time.wHour,time.wMinute,time.wSecond,time.wMilliseconds,GetCurrentProcessId(),GetTickCount64());
    if(!utf8(path,encoded,sizeof encoded)||!at_take_save(&a->take,encoded)) {
        MessageBoxW(owner,L"自动保存失败，行程仍在内存。请用“保存行程”选择其他位置。",L"保留行程",MB_OK|MB_ICONERROR);return 0;
    }
    unsaved=0;return 1;
}
int am_take_record(HWND owner,AmAudio *a,int muted) {
    if(!am_take_preserve(owner,a)||!am_audio_record(a,muted,0))return 0;unsaved=1;return 1;
}
static int dialog(HWND owner,int save,wchar_t *path) {
    OPENFILENAMEW d={0};d.lStructSize=sizeof d;d.hwndOwner=owner;d.lpstrFilter=L"DNA 驾驶行程 (*.vslrun)\0*.vslrun\0\0";
    d.lpstrFile=path;d.nMaxFile=4096;d.lpstrDefExt=L"vslrun";
    d.Flags=OFN_NOCHANGEDIR|OFN_PATHMUSTEXIST|(save?OFN_OVERWRITEPROMPT:OFN_FILEMUSTEXIST);
    return save?GetSaveFileNameW(&d):GetOpenFileNameW(&d);
}
int am_take_save_dialog(HWND owner,AmAudio *a) {
    wchar_t path[4096]=L"DNA驾驶行程.vslrun";char encoded[16384];
    am_audio_stop(a);if(!a->ready||!dialog(owner,1,path))return 0;
    if(!utf8(path,encoded,sizeof encoded)||!at_take_save(&a->take,encoded)) {
        MessageBoxW(owner,L"保存失败，行程仍在内存。",L"保存行程",MB_OK|MB_ICONERROR);return 0;
    }
    unsaved=0;return 1;
}
int am_take_load_dialog(HWND owner,AmAudio *a,int muted) {
    wchar_t path[4096]=L"";char encoded[16384];AtTake candidate={0};
    if(!dialog(owner,0,path))return 0;
    if(!utf8(path,encoded,sizeof encoded)||!at_take_load(&candidate,encoded)||candidate.assets->config.channels!=2) {
        at_take_free(&candidate);MessageBoxW(owner,L"无法载入：文件损坏或与当前算法版本不兼容。",L"载入回放",MB_OK|MB_ICONERROR);return 0;
    }
    if(!am_take_preserve(owner,a)){at_take_free(&candidate);return 0;}
    at_take_free(&a->take);a->take=candidate;a->ready=1;
    return am_audio_replay(a,muted);
}

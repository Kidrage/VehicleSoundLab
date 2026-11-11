#include "bank.h"
#include <commdlg.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
static void add(SmBank *bank,HWND combo,const wchar_t *path){
    wchar_t full[2048];const wchar_t *name;unsigned i;
    if(!GetFullPathNameW(path,2048,full,NULL))return;
    for(i=0;i<bank->count;++i)if(!_wcsicmp(full,bank->paths[i])){SendMessageW(combo,CB_SETCURSEL,i,0);return;}
    if(bank->count>=32)return;wcscpy_s(bank->paths[bank->count],2048,full);name=wcsrchr(full,L'\\');name=name?name+1:full;
    SendMessageW(combo,CB_ADDSTRING,0,(LPARAM)name);SendMessageW(combo,CB_SETCURSEL,bank->count++,0);
}
void sm_bank_fill(SmBank *bank,HWND combo,const wchar_t *initial){
    WIN32_FIND_DATAW data;HANDLE search;wchar_t path[2048];memset(bank,0,sizeof *bank);SendMessageW(combo,CB_RESETCONTENT,0,0);
    search=FindFirstFileW(L"voices\\low_rumble_v2\\*.model",&data);
    if(search!=INVALID_HANDLE_VALUE){do{if(!(data.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)){swprintf(path,2048,L"voices\\low_rumble_v2\\%s",data.cFileName);add(bank,combo,path);}}while(FindNextFileW(search,&data));FindClose(search);}
    add(bank,combo,initial);
}
int sm_bank_load(SmAudio *audio,LrProfile *destination,const wchar_t *path){
    char utf8[8192];LrProfile *candidate;int ok=0;
    if(!WideCharToMultiByte(CP_UTF8,0,path,-1,utf8,sizeof utf8,NULL,NULL))return 0;
    candidate=malloc(sizeof *candidate);if(!candidate)return 0;
    if(lr_profile_load(utf8,candidate)){sm_audio_stop(audio);*destination=*candidate;ok=1;}
    free(candidate);return ok;
}
int sm_bank_choose(SmBank *bank,HWND owner,HWND combo,SmAudio *audio,LrProfile *destination){
    wchar_t path[2048]={0},initial[2048];OPENFILENAMEW file={0};GetFullPathNameW(L"voices\\low_rumble_v2",2048,initial,NULL);
    file.lStructSize=sizeof file;file.hwndOwner=owner;file.lpstrFilter=L"Low rumble model\0*.model\0\0";file.lpstrFile=path;file.nMaxFile=2048;file.lpstrInitialDir=initial;
    file.Flags=OFN_FILEMUSTEXIST|OFN_PATHMUSTEXIST|OFN_NOCHANGEDIR;
    if(!GetOpenFileNameW(&file))return 0;if(!sm_bank_load(audio,destination,path))return -1;
    add(bank,combo,path);return 1;
}

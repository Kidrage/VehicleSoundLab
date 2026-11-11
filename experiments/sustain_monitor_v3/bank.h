#ifndef VSL_DNA_MONITOR_BANK_H
#define VSL_DNA_MONITOR_BANK_H
#include "audio.h"
typedef struct {unsigned count;wchar_t paths[32][2048];} SmBank;
void sm_bank_fill(SmBank *bank,HWND combo,const wchar_t *initial_path);
int sm_bank_load(SmAudio *audio,SdProfile *destination,const wchar_t *path);
int sm_bank_choose(SmBank *bank,HWND owner,HWND combo,SmAudio *audio,SdProfile *destination);
#endif

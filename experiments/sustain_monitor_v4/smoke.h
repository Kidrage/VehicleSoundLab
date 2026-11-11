#ifndef VSL_SUSTAIN_MONITOR_SMOKE_H
#define VSL_SUSTAIN_MONITOR_SMOKE_H
#include "audio.h"
typedef struct {int enabled,stage,passed,isolated;SmStats baseline,live,stopped;} SmSmoke;
int sm_smoke_prepare(SmSmoke *test,SmAudio *audio);
void sm_smoke_tick(SmSmoke *test,SmAudio *audio,HWND window,HWND pitch,HWND detail,HWND level,HWND rumble,HWND mode);
void sm_smoke_finish(SmSmoke *test,SmAudio *audio,HWND window);
#endif

#ifndef VSL_RESONANT_MONITOR_UI_CHECKS_H
#define VSL_RESONANT_MONITOR_UI_CHECKS_H
#include "audio.h"
typedef struct {int enabled,stage,passed,controls_ok;wchar_t directory[2048];} RsmUiChecks;
void rsm_ui_checks_tick(RsmUiChecks *checks,HWND owner,RsmAudio *audio);
void rsm_ui_checks_finish(RsmUiChecks *checks,RsmAudio *audio);
#endif

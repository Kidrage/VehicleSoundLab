#ifndef VSL_SCENE_MONITOR_UI_CHECKS_H
#define VSL_SCENE_MONITOR_UI_CHECKS_H
#include "audio.h"
typedef struct { int enabled, stage, passed, controls_ok; wchar_t directory[2048]; } SmoUiChecks;
void smo_ui_checks_tick(SmoUiChecks *checks, HWND owner, SaAudio *audio);
void smo_ui_checks_finish(SmoUiChecks *checks, SaAudio *audio);
#endif

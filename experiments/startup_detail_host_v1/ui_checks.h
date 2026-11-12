#ifndef VSL_STARTUP_DETAIL_UI_CHECKS_H
#define VSL_STARTUP_DETAIL_UI_CHECKS_H
#include "../atlas_monitor_v1/audio.h"
#include "../atlas_monitor_v1/models.h"
/* Own-window programmatic binding checks; no screenshot or listening claim. */
int am_startup_detail_ui_check(HWND window,AmAudio *audio,AmModels *models,int detail_study,const wchar_t *report_path);
#endif

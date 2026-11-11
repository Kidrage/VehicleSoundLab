#ifndef VSL_TUNING_H
#define VSL_TUNING_H
#include <windows.h>
#include "core/types.h"
HWND vsl_tuning_show(HWND owner,HFONT font,VslParams *params);
void vsl_tuning_sync(void);
void vsl_tuning_enable(int enabled);
void vsl_tuning_meters(const VslVoicing *voice,int pure,int running);
#define VSL_TUNING_CHANGED (WM_APP+17)
#endif

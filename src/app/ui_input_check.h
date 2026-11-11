#ifndef VSL_UI_INPUT_CHECK_H
#define VSL_UI_INPUT_CHECK_H
#include <windows.h>
#include "core/types.h"
typedef struct {
    int phase,gear;
    int type_search,selection_no_pedal,mode_no_shift;
    int brake_shortcut,brake_release,throttle_shortcut,throttle_release,focus_release;
} VslUiInputCheck;
/* Self-test of this application's own message loop. No system input injection. */
int vsl_ui_input_tick(VslUiInputCheck *check,HWND root,HWND profile,HWND mode,
    HWND monitor,VslParams *params,int throttle_held,int brake_held,
    const wchar_t *workspace,void (*capture)(const wchar_t *name));
#endif

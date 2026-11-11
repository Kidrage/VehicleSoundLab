#define _CRT_SECURE_NO_WARNINGS
#include "ui_input_check.h"
#include "version.h"
#include <stdio.h>

static void down(HWND target,int key) { PostMessageW(target,WM_KEYDOWN,key,1); }
static void up(HWND target,int key) { PostMessageW(target,WM_KEYUP,key,(LPARAM)0xc0000001); }
int vsl_ui_input_tick(VslUiInputCheck *s,HWND root,HWND profile,HWND mode,
    HWND monitor,VslParams *p,int throttle,int brake,const wchar_t *workspace,
    void (*capture)(const wchar_t *name)) {
    switch(s->phase++) {
    case 0: SetFocus(profile);down(profile,'S');break;
    case 1:
        s->type_search=SendMessageW(profile,CB_GETCURSEL,0,0)==VSL_SCIFI&&p->profile==VSL_SCIFI;
        s->selection_no_pedal=p->brake==0&&!brake;
        capture(L"ui_input_type_search.bmp");up(profile,'S');break;
    case 2: s->gear=p->gear;SetFocus(mode);down(mode,'E');break;
    case 3: s->mode_no_shift=p->gear==s->gear&&p->drive_mode==VSL_PEDALS;up(mode,'E');break;
    case 4: SetFocus(monitor);down(monitor,'S');break;
    case 5:
        s->brake_shortcut=p->brake==1&&brake;
        SetFocus(profile);up(profile,'S');break;
    case 6:
        s->brake_release=p->brake==0&&!brake;
        SetFocus(monitor);down(monitor,'W');break;
    case 7:
        s->throttle_shortcut=p->throttle==1&&throttle;
        SetFocus(mode);up(mode,'W');break;
    case 8:
        s->throttle_release=p->throttle==0&&!throttle;
        SetFocus(monitor);down(monitor,'S');break;
    case 9: SendMessageW(root,WM_ACTIVATE,WA_INACTIVE,0);break;
    case 10: {
        wchar_t path[MAX_PATH];FILE *f;
        s->focus_release=p->brake==0&&!brake&&p->throttle==0&&!throttle;
        capture(L"ui_input_ready.bmp");
        swprintf(path,MAX_PATH,L"%s\\renders\\%s\\ui_input.json",workspace,VSL_DIAGNOSTIC_FOLDER_W);
        f=_wfopen(path,L"w");
        if(f) {
            fprintf(f,"{\"app\":\"%s\",\"dsp\":\"%s\",\"SCI_FI_type_search\":%d,\"selection_does_not_brake\":%d,\"mode_selection_does_not_shift\":%d,\"brake_shortcut\":%d,\"brake_release_after_focus_change\":%d,\"throttle_shortcut\":%d,\"throttle_release_after_focus_change\":%d,\"focus_loss_releases_pedals\":%d,\"system_input_injection\":false}\n",
                VSL_APP_VERSION,VSL_VERSION,s->type_search,s->selection_no_pedal,s->mode_no_shift,
                s->brake_shortcut,s->brake_release,s->throttle_shortcut,s->throttle_release,s->focus_release);
            fclose(f);
        }
        return 1;
    }
    }
    return 0;
}

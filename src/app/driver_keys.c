#include "driver_keys.h"
#include <wchar.h>

static int owns_character_input(HWND root,HWND control) {
    while(control&&control!=root) {
        wchar_t name[80]={0};
        GetClassNameW(control,name,80);
        if(!_wcsicmp(name,L"ComboBox")||!_wcsicmp(name,L"ComboLBox")||
           !_wcsicmp(name,L"Edit")||!_wcsicmp(name,L"ListBox")||
           !_wcsnicmp(name,L"RichEdit",8))return 1;
        control=GetParent(control);
    }
    return 0;
}

VslDriverKey vsl_driver_key(HWND root,const MSG *m,int enabled,int throttle,int brake) {
    int key=(int)m->wParam;
    if((m->message!=WM_KEYDOWN&&m->message!=WM_KEYUP)||
       (m->hwnd!=root&&!IsChild(root,m->hwnd)))return VSL_KEY_NONE;
    if(m->message==WM_KEYUP) {
        if(key=='W'&&throttle)return VSL_KEY_THROTTLE_UP;
        if(key=='S'&&brake)return VSL_KEY_BRAKE_UP;
        return VSL_KEY_NONE;
    }
    if(!enabled||owns_character_input(root,m->hwnd))return VSL_KEY_NONE;
    if(key=='W')return VSL_KEY_THROTTLE_DOWN;
    if(key=='S')return VSL_KEY_BRAKE_DOWN;
    if(key=='Q'||key=='E') {
        if(m->lParam&(1L<<30))return VSL_KEY_CONSUMED;
        return key=='Q'?VSL_KEY_GEAR_DOWN:VSL_KEY_GEAR_UP;
    }
    return VSL_KEY_NONE;
}

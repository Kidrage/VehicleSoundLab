#ifdef NDEBUG
#undef NDEBUG
#endif
#include "app/driver_keys.h"
#include <assert.h>
#include <stdio.h>

static VslDriverKey key(HWND root,HWND target,UINT type,int code,int enabled,
                        int throttle,int brake,int repeated) {
    MSG m={0};m.hwnd=target;m.message=type;m.wParam=code;
    m.lParam=repeated?(1L<<30):0;
    return vsl_driver_key(root,&m,enabled,throttle,brake);
}
int main(void) {
    WNDCLASSW cls={0};HWND root,other,combo,edit,list,button;int i;
    const int keys[]={'W','S','Q','E'};
    cls.lpfnWndProc=DefWindowProcW;cls.hInstance=GetModuleHandleW(NULL);cls.lpszClassName=L"VslKeyContract";
    assert(RegisterClassW(&cls));
    root=CreateWindowW(cls.lpszClassName,L"",0,0,0,600,400,NULL,NULL,cls.hInstance,NULL);
    other=CreateWindowW(cls.lpszClassName,L"",0,0,0,100,100,NULL,NULL,cls.hInstance,NULL);
    combo=CreateWindowW(L"COMBOBOX",L"",WS_CHILD|CBS_DROPDOWNLIST,0,0,200,200,root,NULL,cls.hInstance,NULL);
    edit=CreateWindowW(L"EDIT",L"",WS_CHILD,0,0,200,20,root,NULL,cls.hInstance,NULL);
    list=CreateWindowW(L"LISTBOX",L"",WS_CHILD,0,0,200,100,root,NULL,cls.hInstance,NULL);
    button=CreateWindowW(L"BUTTON",L"",WS_CHILD,0,0,100,30,root,NULL,cls.hInstance,NULL);
    assert(root&&other&&combo&&edit&&list&&button);
    for(i=0;i<4;++i) {
        assert(key(root,combo,WM_KEYDOWN,keys[i],1,0,0,0)==VSL_KEY_NONE);
        assert(key(root,edit,WM_KEYDOWN,keys[i],1,0,0,0)==VSL_KEY_NONE);
        assert(key(root,list,WM_KEYDOWN,keys[i],1,0,0,0)==VSL_KEY_NONE);
        assert(key(root,other,WM_KEYDOWN,keys[i],1,1,1,0)==VSL_KEY_NONE);
        assert(key(root,button,WM_KEYDOWN,keys[i],0,0,0,0)==VSL_KEY_NONE);
        assert(key(root,button,WM_CHAR,keys[i],1,0,0,0)==VSL_KEY_NONE);
    }
    assert(key(root,root,WM_KEYDOWN,'W',1,0,0,0)==VSL_KEY_THROTTLE_DOWN);
    assert(key(root,button,WM_KEYDOWN,'S',1,0,0,0)==VSL_KEY_BRAKE_DOWN);
    assert(key(root,button,WM_KEYDOWN,'Q',1,0,0,0)==VSL_KEY_GEAR_DOWN);
    assert(key(root,button,WM_KEYDOWN,'E',1,0,0,0)==VSL_KEY_GEAR_UP);
    assert(key(root,button,WM_KEYDOWN,'E',1,0,0,1)==VSL_KEY_CONSUMED);
    assert(key(root,combo,WM_KEYUP,'W',1,1,0,0)==VSL_KEY_THROTTLE_UP);
    assert(key(root,edit,WM_KEYUP,'S',0,0,1,0)==VSL_KEY_BRAKE_UP);
    assert(key(root,combo,WM_KEYUP,'S',1,0,0,0)==VSL_KEY_NONE);
    assert(key(root,other,WM_KEYUP,'W',1,1,0,0)==VSL_KEY_NONE);
    DestroyWindow(root);DestroyWindow(other);
    puts("Driver keys respect text controls, preserve pedal releases and suppress repeated shifts.");
    return 0;
}

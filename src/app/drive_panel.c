#include "drive_panel.h"
#include <windowsx.h>
static HWND ignition,automatic,backfire;
static HWND button(HWND parent,HFONT font,const wchar_t *name,int x,int y,int w,int id,int check) {
    HWND h=CreateWindowW(L"BUTTON",name,WS_CHILD|WS_VISIBLE|WS_TABSTOP|(check?BS_AUTOCHECKBOX:BS_OWNERDRAW),x,y,w,30,parent,(HMENU)(INT_PTR)id,GetModuleHandle(NULL),NULL);
    SendMessageW(h,WM_SETFONT,(WPARAM)font,TRUE);return h;
}
void vsl_drive_panel_create(HWND p,HFONT f,int y) {
    ignition=button(p,f,L"Ignition",28,y,110,ID_IGNITION,1);
    button(p,f,L"Start",151,y,90,ID_START,0);
    button(p,f,L"Gear -",258,y,85,ID_GEAR_DOWN,0);button(p,f,L"N",355,y,55,ID_NEUTRAL,0);
    button(p,f,L"Gear +",422,y,85,ID_GEAR_UP,0);
    automatic=button(p,f,L"Auto gears",540,y,145,ID_AUTOGEAR,1);
    backfire=button(p,f,L"Overrun events",710,y,190,ID_BACKFIRE,1);
}
void vsl_drive_panel_sync(const VslParams *p) {
    Button_SetCheck(ignition,p->ignition);Button_SetCheck(automatic,p->auto_gear);Button_SetCheck(backfire,p->backfire);
}
int vsl_drive_panel_command(int id,VslParams *p,int gear) {
    switch(id) {
    case ID_IGNITION:p->ignition=Button_GetCheck(ignition)==BST_CHECKED;break;
    case ID_START:p->ignition=1;++p->start_id;break;
    case ID_NEUTRAL:p->gear=0;p->auto_gear=0;break;
    case ID_GEAR_DOWN:p->gear=gear>1?gear-1:0;p->auto_gear=0;break;
    case ID_GEAR_UP:p->gear=gear<7?gear+1:7;p->auto_gear=0;break;
    case ID_AUTOGEAR:p->auto_gear=Button_GetCheck(automatic)==BST_CHECKED;break;
    case ID_BACKFIRE:p->backfire=Button_GetCheck(backfire)==BST_CHECKED;break;
    default:return 0;
    }
    vsl_drive_panel_sync(p);return 1;
}

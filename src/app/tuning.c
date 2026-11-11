#include "tuning.h"
#include <commctrl.h>
#include <stdio.h>
#include <windowsx.h>
static HWND panel,owner,sliders[8],labels[8];static VslParams *params;static HFONT font;
static HWND meters[6];
static HWND fuel_switch,pumping_slider,pumping_label,mechanical_switch,combustion_switch,propagation_switch;
static HWND character_sliders[4],character_labels[4];
static HWND source_selector,pulse_slider,pulse_label;
static int controls_enabled=1;
static const wchar_t *names[]={L"Brightness",L"High firing orders",L"Intake detail",L"Mechanical detail",L"Idle body",L"Cycle irregularity",L"Release body hold",L"Event level"};
static double *value(int i) {
    double *v[]={&params->brightness,&params->detail,&params->intake,&params->mechanical,
        &params->idle_body,&params->irregularity,&params->release_time,&params->event_level};return v[i];
}
static void label_values(void) {
    int i;for(i=0;i<8;++i) { wchar_t text[128];swprintf(text,128,i==6?L"%s    %.0f ms":L"%s    %.0f%%",names[i],*value(i)*(i==6?1000:100));SetWindowTextW(labels[i],text); }
    { wchar_t text[100];swprintf(text,100,L"Motored exhaust    %.0f%%",params->pumping*100);SetWindowTextW(pumping_label,text); }
    { wchar_t text[100];swprintf(text,100,L"Combustion texture (test)    %.0f%%",params->pressure_texture*100);SetWindowTextW(character_labels[0],text);
      swprintf(text,100,L"Mechanical transfer (test)    %.0f%%",params->structure_transfer*100);SetWindowTextW(character_labels[1],text);
      swprintf(text,100,L"Response shape (test)    %.0f%%",params->response_shape*100);SetWindowTextW(character_labels[2],text);
      swprintf(text,100,L"Main pressure shape (test)    %.0f%%",params->event_color*100);SetWindowTextW(character_labels[3],text);
      swprintf(text,100,L"Combustion source mix    %.0f%%",params->pulse_amount*100);SetWindowTextW(pulse_label,text); }
}
static LRESULT CALLBACK procedure(HWND h,UINT m,WPARAM w,LPARAM l) {
    int i;(void)w;(void)l;
    if(!controls_enabled&&(m==WM_HSCROLL||m==WM_COMMAND))return 0;
    if(m==WM_MEASUREITEM&&((MEASUREITEMSTRUCT*)l)->CtlID==110) {
        ((MEASUREITEMSTRUCT*)l)->itemHeight=24;return TRUE;
    }
    if(m==WM_DRAWITEM&&((DRAWITEMSTRUCT*)l)->CtlID==110) {
        DRAWITEMSTRUCT *d=(DRAWITEMSTRUCT*)l;RECT r=d->rcItem;wchar_t text[128]={0};
        int selected=d->itemID==(UINT)-1?(int)SendMessageW(d->hwndItem,CB_GETCURSEL,0,0):(int)d->itemID;
        HGDIOBJ old=SelectObject(d->hDC,font);
        FillRect(d->hDC,&r,GetSysColorBrush(d->itemState&ODS_SELECTED?COLOR_HIGHLIGHT:COLOR_WINDOW));
        SetTextColor(d->hDC,GetSysColor(d->itemState&ODS_SELECTED?COLOR_HIGHLIGHTTEXT:COLOR_WINDOWTEXT));
        SetBkMode(d->hDC,TRANSPARENT);r.left+=5;
        if(selected!=CB_ERR)SendMessageW(d->hwndItem,CB_GETLBTEXT,selected,(LPARAM)text);
        DrawTextW(d->hDC,text,-1,&r,DT_SINGLELINE|DT_VCENTER);
        if(d->itemState&ODS_FOCUS)DrawFocusRect(d->hDC,&r);
        SelectObject(d->hDC,old);return TRUE;
    }
    if(m==WM_CREATE) {
        for(i=0;i<8;++i) {
            int x=20+(i/4)*320,y=18+(i%4)*70;
            labels[i]=CreateWindowW(L"STATIC",names[i],WS_CHILD|WS_VISIBLE,x,y,300,22,h,NULL,NULL,NULL);
            SendMessageW(labels[i],WM_SETFONT,(WPARAM)font,TRUE);
            sliders[i]=CreateWindowW(TRACKBAR_CLASSW,L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|TBS_NOTICKS,x-4,y+24,300,30,h,NULL,NULL,NULL);
            SendMessageW(sliders[i],TBM_SETRANGE,TRUE,MAKELPARAM(0,1000));
        }
        {
            static const wchar_t *layer[]={L"Exhaust",L"Body",L"Intake",L"Mechanical",L"Air",L"High orders"};
            HWND title=CreateWindowW(L"STATIC",L"Layer activity (control envelopes)",WS_CHILD|WS_VISIBLE,20,300,400,22,h,NULL,NULL,NULL);
            SendMessageW(title,WM_SETFONT,(WPARAM)font,TRUE);
            for(i=0;i<6;++i) {
                HWND label=CreateWindowW(L"STATIC",layer[i],WS_CHILD|WS_VISIBLE,20+i*104,329,100,22,h,NULL,NULL,NULL);
                SendMessageW(label,WM_SETFONT,(WPARAM)font,TRUE);
                meters[i]=CreateWindowW(PROGRESS_CLASSW,L"",WS_CHILD|WS_VISIBLE,20+i*104,355,94,9,h,NULL,NULL,NULL);
                SendMessageW(meters[i],PBM_SETRANGE32,0,1000);
            }
        }
        fuel_switch=CreateWindowW(L"BUTTON",L"Overrun fuel cut",WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_AUTOCHECKBOX,20,392,285,28,h,(HMENU)101,NULL,NULL);
        pumping_label=CreateWindowW(L"STATIC",L"Motored exhaust",WS_CHILD|WS_VISIBLE,340,382,300,22,h,NULL,NULL,NULL);
        pumping_slider=CreateWindowW(TRACKBAR_CLASSW,L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|TBS_NOTICKS,336,406,300,30,h,(HMENU)102,NULL,NULL);
        SendMessageW(fuel_switch,WM_SETFONT,(WPARAM)font,TRUE);SendMessageW(pumping_label,WM_SETFONT,(WPARAM)font,TRUE);
        SendMessageW(pumping_slider,TBM_SETRANGE,TRUE,MAKELPARAM(0,1000));
        mechanical_switch=CreateWindowW(L"BUTTON",L"Driven mechanical resonators",WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_AUTOCHECKBOX,20,422,300,26,h,(HMENU)103,NULL,NULL);
        SendMessageW(mechanical_switch,WM_SETFONT,(WPARAM)font,TRUE);
        combustion_switch=CreateWindowW(L"BUTTON",L"Per-firing pressure variation",WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_AUTOCHECKBOX,340,444,300,26,h,(HMENU)104,NULL,NULL);
        SendMessageW(combustion_switch,WM_SETFONT,(WPARAM)font,TRUE);
        propagation_switch=CreateWindowW(L"BUTTON",L"Source distance / stereo depth",WS_CHILD|WS_VISIBLE|WS_TABSTOP|BS_AUTOCHECKBOX,20,450,310,26,h,(HMENU)105,NULL,NULL);
        SendMessageW(propagation_switch,WM_SETFONT,(WPARAM)font,TRUE);
        for(i=0;i<4;++i) {
            int x=20+(i%2)*320,y=488+(i/2)*66;
            character_labels[i]=CreateWindowW(L"STATIC",L"",WS_CHILD|WS_VISIBLE,x,y,310,22,h,NULL,NULL,NULL);
            SendMessageW(character_labels[i],WM_SETFONT,(WPARAM)font,TRUE);
            character_sliders[i]=CreateWindowW(TRACKBAR_CLASSW,L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|TBS_NOTICKS,x-4,y+24,300,30,h,(HMENU)(INT_PTR)(106+i),NULL,NULL);
            SendMessageW(character_sliders[i],TBM_SETRANGE,TRUE,MAKELPARAM(0,1000));
        }
        {
            HWND title=CreateWindowW(L"STATIC",L"Pressure source",WS_CHILD|WS_VISIBLE,20,620,300,22,h,NULL,NULL,NULL);
            SendMessageW(title,WM_SETFONT,(WPARAM)font,TRUE);
            source_selector=CreateWindowW(L"COMBOBOX",L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|CBS_DROPDOWNLIST|CBS_OWNERDRAWFIXED|CBS_HASSTRINGS|WS_VSCROLL,20,644,295,130,h,(HMENU)110,NULL,NULL);
            SendMessageW(source_selector,WM_SETFONT,(WPARAM)font,TRUE);
            SendMessageW(source_selector,CB_ADDSTRING,0,(LPARAM)L"Original OSC");
            SendMessageW(source_selector,CB_ADDSTRING,0,(LPARAM)L"Fixed combustion events");
            SendMessageW(source_selector,CB_ADDSTRING,0,(LPARAM)L"Variable combustion events");
            pulse_label=CreateWindowW(L"STATIC",L"",WS_CHILD|WS_VISIBLE,340,620,300,22,h,NULL,NULL,NULL);
            SendMessageW(pulse_label,WM_SETFONT,(WPARAM)font,TRUE);
            pulse_slider=CreateWindowW(TRACKBAR_CLASSW,L"",WS_CHILD|WS_VISIBLE|WS_TABSTOP|TBS_NOTICKS,336,644,300,30,h,(HMENU)111,NULL,NULL);
            SendMessageW(pulse_slider,TBM_SETRANGE,TRUE,MAKELPARAM(0,1000));
        }
        return 0;
    }
    if(m==WM_HSCROLL) {
        for(i=0;i<8;++i)if((HWND)l==sliders[i]) {
            double x=SendMessageW(sliders[i],TBM_GETPOS,0,0)/1000.;*value(i)=i==6?.08+1.12*x:x;
        }
        if((HWND)l==pumping_slider)params->pumping=SendMessageW(pumping_slider,TBM_GETPOS,0,0)/1000.;
        if((HWND)l==character_sliders[0])params->pressure_texture=SendMessageW(character_sliders[0],TBM_GETPOS,0,0)/1000.;
        if((HWND)l==character_sliders[1])params->structure_transfer=SendMessageW(character_sliders[1],TBM_GETPOS,0,0)/1000.;
        if((HWND)l==character_sliders[2])params->response_shape=SendMessageW(character_sliders[2],TBM_GETPOS,0,0)/1000.;
        if((HWND)l==character_sliders[3])params->event_color=SendMessageW(character_sliders[3],TBM_GETPOS,0,0)/1000.;
        if((HWND)l==pulse_slider)params->pulse_amount=SendMessageW(pulse_slider,TBM_GETPOS,0,0)/1000.;
        label_values();SendMessageW(owner,VSL_TUNING_CHANGED,0,0);return 0;
    }
    if(m==WM_COMMAND && LOWORD(w)==101) {
        params->fuel_cut=Button_GetCheck(fuel_switch)==BST_CHECKED;
        SendMessageW(owner,VSL_TUNING_CHANGED,0,0);return 0;
    }
    if(m==WM_COMMAND && LOWORD(w)==103) {
        params->mechanical_model=Button_GetCheck(mechanical_switch)==BST_CHECKED;
        SendMessageW(owner,VSL_TUNING_CHANGED,0,0);return 0;
    }
    if(m==WM_COMMAND && LOWORD(w)==104) {
        params->combustion_variation=Button_GetCheck(combustion_switch)==BST_CHECKED;
        SendMessageW(owner,VSL_TUNING_CHANGED,0,0);return 0;
    }
    if(m==WM_COMMAND && LOWORD(w)==105) {
        params->propagation=Button_GetCheck(propagation_switch)==BST_CHECKED;
        SendMessageW(owner,VSL_TUNING_CHANGED,0,0);return 0;
    }
    if(m==WM_COMMAND && LOWORD(w)==110 && HIWORD(w)==CBN_SELCHANGE) {
        LRESULT selected=SendMessageW(source_selector,CB_GETCURSEL,0,0);
        if(selected>=VSL_SOURCE_OSC&&selected<=VSL_SOURCE_VARIABLE)params->firing_source=(int)selected;
        SendMessageW(owner,VSL_TUNING_CHANGED,0,0);return 0;
    }
    if(m==WM_CLOSE) { ShowWindow(h,SW_HIDE);return 0; }
    if(m==WM_DESTROY) { panel=NULL;return 0; }
    return DefWindowProcW(h,m,w,l);
}
void vsl_tuning_sync(void) {
    int i;if(!panel||!params)return;
    for(i=0;i<8;++i)SendMessageW(sliders[i],TBM_SETPOS,TRUE,(LPARAM)((i==6?(*value(i)-.08)/1.12:*value(i))*1000));
    SendMessageW(pumping_slider,TBM_SETPOS,TRUE,(LPARAM)(params->pumping*1000));
    SendMessageW(character_sliders[0],TBM_SETPOS,TRUE,(LPARAM)(params->pressure_texture*1000));
    SendMessageW(character_sliders[1],TBM_SETPOS,TRUE,(LPARAM)(params->structure_transfer*1000));
    SendMessageW(character_sliders[2],TBM_SETPOS,TRUE,(LPARAM)(params->response_shape*1000));
    SendMessageW(character_sliders[3],TBM_SETPOS,TRUE,(LPARAM)(params->event_color*1000));
    SendMessageW(source_selector,CB_SETCURSEL,params->firing_source,0);
    SendMessageW(pulse_slider,TBM_SETPOS,TRUE,(LPARAM)(params->pulse_amount*1000));
    Button_SetCheck(fuel_switch,params->fuel_cut);
    Button_SetCheck(mechanical_switch,params->mechanical_model);
    Button_SetCheck(combustion_switch,params->combustion_variation);
    Button_SetCheck(propagation_switch,params->propagation);
    label_values();
}
void vsl_tuning_enable(int enabled) { controls_enabled=enabled;if(panel)EnableWindow(panel,enabled); }
HWND vsl_tuning_show(HWND parent,HFONT f,VslParams *p) {
    owner=parent;font=f;params=p;
    if(!panel) {
        RECT size={0,0,660,692};DWORD style=WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU;
        WNDCLASSW c={0};c.lpfnWndProc=procedure;c.hInstance=GetModuleHandle(NULL);c.lpszClassName=L"VslTuning";c.hCursor=LoadCursor(NULL,IDC_ARROW);c.hbrBackground=(HBRUSH)(COLOR_BTNFACE+1);RegisterClassW(&c);
        AdjustWindowRect(&size,style,FALSE);
        panel=CreateWindowW(c.lpszClassName,L"Sound detail",style, CW_USEDEFAULT,CW_USEDEFAULT,size.right-size.left,size.bottom-size.top,parent,NULL,c.hInstance,NULL);
    }
    vsl_tuning_sync();
    if(IsWindowVisible(parent)) { ShowWindow(panel,SW_SHOW);SetForegroundWindow(panel); }
    return panel;
}
void vsl_tuning_meters(const VslVoicing *v,int pure,int running) {
    double values[]={v->dna_gain,v->body_gain,v->intake_gain*3,v->mechanical_gain*10,v->air_gain*7,v->high_gain};int i;
    if(v->mechanical_motion_gain*10>values[3])values[3]=v->mechanical_motion_gain*10;
    if(!panel)return;
    for(i=0;i<6;++i) {
        double value=running&&(!pure||i==0||i==5)?values[i]:0;
        if(value<0)value=0;if(value>1)value=1;
        SendMessageW(meters[i],PBM_SETPOS,(WPARAM)(value*1000),0);
    }
}

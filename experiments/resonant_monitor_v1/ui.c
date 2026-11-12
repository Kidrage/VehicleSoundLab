#define _CRT_SECURE_NO_WARNINGS
#include "audio.h"
#include "ui_checks.h"
#include <commctrl.h>
#include <shellapi.h>
#include <math.h>
#include <stdio.h>
static RsmAssets assets;static RsmAudio audio;static RsmUiChecks checks;
static HWND sliders[4],labels[4],bank,status,hint;static HFONT font,heading;
static HWND item(HWND w,const wchar_t *kind,const wchar_t *text,DWORD style,int id,int x,int y,int width,int height) {
    HWND h=CreateWindowW(kind,text,WS_CHILD|WS_VISIBLE|style,x,y,width,height,w,(HMENU)(INT_PTR)id,NULL,NULL);
    SendMessageW(h,WM_SETFONT,(WPARAM)font,TRUE);return h;
}
static void controls(void) {
    int v[4],i;wchar_t text[120];RsmControl p=rsm_audio_get(&audio);
    for(i=0;i<4;++i)v[i]=(int)SendMessageW(sliders[i],TBM_GETPOS,0,0);
    p.source.source.pitch=v[0]/1000.;p.source.detail_gain=assets.has_detail?v[1]/100.:0;
    p.source.source.low_gain=assets.has_low?v[2]/100.:0;p.gain=.5*pow(10,v[3]/20.);
    rsm_audio_control(&audio,&p);
    swprintf(text,120,L"音高    ×%.2f",p.source.source.pitch);SetWindowTextW(labels[0],text);
    swprintf(text,120,L"连续细节    %d%%",assets.has_detail?v[1]:0);SetWindowTextW(labels[1],text);
    if(assets.has_low)swprintf(text,120,L"相干低频    %d%%",v[2]);else wcscpy_s(text,120,L"独立低频    此配方未配");
    SetWindowTextW(labels[2],text);swprintf(text,120,L"输出    %d dB",v[3]);SetWindowTextW(labels[3],text);
    EnableWindow(sliders[1],assets.has_detail);EnableWindow(sliders[2],assets.has_low);
}
static void reset_controls(void) {
    int values[]={1000,assets.has_detail?100:0,assets.has_low?100:0,0},i;
    for(i=0;i<4;++i)SendMessageW(sliders[i],TBM_SETPOS,TRUE,values[i]);controls();
}
static int select_voice(HWND w,int selection) {
    RssConfig cfg;RsmControl p;
    rsm_audio_stop(&audio);
    if(!rsm_assets_load(&assets,selection)){MessageBoxW(w,L"配方加载失败，请从项目根目录启动。",L"声源监听",MB_OK|MB_ICONERROR);return 0;}
    cfg=rsm_assets_config(&assets);p=rsm_assets_control(&assets);rsm_audio_rebind(&audio,&cfg,&p);reset_controls();
    SetWindowTextW(hint,selection<3?L"驻车低转候选 · 实际转速未确认":L"车外行驶 · 固定情境配方");
    SetWindowTextW(status,L"已停止");return 1;
}
static LRESULT CALLBACK procedure(HWND w,UINT message,WPARAM wp,LPARAM lp) {
    switch(message) {
    case WM_CREATE: {
        int minimum[]={900,0,0,-18},maximum[]={1100,100,100,0},i;
        const wchar_t *names[]={L"低转 · 原版",L"低转 · 补细节（待评）",L"低转 · 轻量替换（待评）",L"行驶 · 原版",L"行驶 · 保留35%"};
        font=CreateFontW(-17,0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        heading=CreateFontW(-24,0,0,0,FW_SEMIBOLD,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        SendMessageW(item(w,L"STATIC",L"声源监听",0,0,24,18,475,34),WM_SETFONT,(WPARAM)heading,TRUE);
        bank=item(w,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP,40,24,66,475,200);
        for(i=0;i<5;++i)SendMessageW(bank,CB_ADDSTRING,0,(LPARAM)names[i]);SendMessageW(bank,CB_SETCURSEL,1,0);
        hint=item(w,L"STATIC",L"驻车低转候选 · 实际转速未确认",0,0,24,103,475,25);
        for(i=0;i<4;++i) {
            labels[i]=item(w,L"STATIC",L"",0,0,24,143+i*62,475,25);
            sliders[i]=item(w,TRACKBAR_CLASSW,L"",TBS_HORZ|TBS_NOTICKS|WS_TABSTOP,20+i,24,168+i*62,475,29);
            SendMessageW(sliders[i],TBM_SETRANGEMIN,FALSE,minimum[i]);SendMessageW(sliders[i],TBM_SETRANGEMAX,TRUE,maximum[i]);
        }
        item(w,L"BUTTON",L"播放／重新开始",BS_PUSHBUTTON|WS_TABSTOP,10,24,408,190,38);
        item(w,L"BUTTON",L"停止",BS_PUSHBUTTON|WS_TABSTOP,11,226,408,125,38);
        item(w,L"BUTTON",L"重置参数",BS_PUSHBUTTON|WS_TABSTOP,12,363,408,136,38);
        status=item(w,L"STATIC",L"已停止",0,0,24,462,475,26);reset_controls();SetTimer(w,1,100,NULL);return 0;
    }
    case WM_HSCROLL:controls();return 0;
    case WM_COMMAND:
        if(LOWORD(wp)==40&&HIWORD(wp)==CBN_SELCHANGE)select_voice(w,(int)SendMessageW(bank,CB_GETCURSEL,0,0));
        else if(LOWORD(wp)==10) {
            if(!rsm_audio_start(&audio,checks.enabled,checks.enabled?240000:0))MessageBoxW(w,L"无法启动监听。",L"声源监听",MB_OK|MB_ICONERROR);
        } else if(LOWORD(wp)==11){rsm_audio_stop(&audio);SetWindowTextW(status,L"已停止");}
        else if(LOWORD(wp)==12)reset_controls();return 0;
    case WM_TIMER: {
        WoStats s=wo_stats(&audio.device);wchar_t text[160];
        if(audio.device.running){swprintf(text,160,L"播放中    %.1f 秒",s.frames/48000.);SetWindowTextW(status,text);}
        else if(s.error[0])SetWindowTextW(status,s.error);
        else SetWindowTextW(status,L"已停止");
        rsm_ui_checks_tick(&checks,w,&audio);return 0;
    }
    case WM_CLOSE:DestroyWindow(w);return 0;
    case WM_DESTROY:
        KillTimer(w,1);rsm_audio_stop(&audio);rsm_ui_checks_finish(&checks,&audio);rsm_audio_destroy(&audio);
        DeleteObject(font);DeleteObject(heading);PostQuitMessage(0);return 0;
    }return DefWindowProcW(w,message,wp,lp);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR command,int show) {
    WNDCLASSW cls={0};HWND w;MSG msg;INITCOMMONCONTROLSEX common={sizeof common,ICC_BAR_CLASSES};
    RssConfig cfg;RsmControl p;int argc;wchar_t **args=CommandLineToArgvW(GetCommandLineW(),&argc);
    (void)previous;(void)command;
    if(argc==3&&!wcscmp(args[1],L"--ui-checks")){checks.enabled=1;wcsncpy_s(checks.directory,2048,args[2],_TRUNCATE);}
    else if(argc!=1){LocalFree(args);return 2;}LocalFree(args);
    if(!rsm_assets_load(&assets,1)){MessageBoxW(NULL,L"请从VehicleSoundLab项目根目录启动。",L"声源监听",MB_OK|MB_ICONERROR);return 2;}
    cfg=rsm_assets_config(&assets);p=rsm_assets_control(&assets);rsm_audio_init(&audio,&cfg,&p);
    InitCommonControlsEx(&common);cls.lpfnWndProc=procedure;cls.hInstance=instance;cls.hCursor=LoadCursor(NULL,IDC_ARROW);
    cls.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);cls.lpszClassName=L"VslResonantSourceMonitor";RegisterClassW(&cls);
    w=CreateWindowExW(WS_EX_CONTROLPARENT,cls.lpszClassName,L"Vehicle Sound Lab · Resonant Source",
        WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,CW_USEDEFAULT,CW_USEDEFAULT,540,540,NULL,NULL,instance,NULL);
    if(!w){rsm_audio_destroy(&audio);return 2;}ShowWindow(w,show);UpdateWindow(w);
    while(GetMessageW(&msg,NULL,0,0)>0)if(!IsDialogMessageW(w,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}
    return checks.enabled&&!checks.passed?1:0;
}

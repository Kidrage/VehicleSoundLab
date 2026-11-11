#define _CRT_SECURE_NO_WARNINGS
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <commctrl.h>
#include <shellapi.h>
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "audio.h"
#include "smoke.h"
#include "bank.h"
static SdProfile model;static SmAudio audio;static SmSmoke smoke;
static SmBank bank;static HWND voices;static wchar_t initial_path[2048];static int bank_checks,last_voice;
static HWND pitch,detail,level,pitch_label,detail_label,level_label,status;static HFONT font;
static HWND control(HWND w,const wchar_t *type,const wchar_t *text,DWORD style,int id,int x,int y,int width,int height){
    HWND child=CreateWindowW(type,text,WS_CHILD|WS_VISIBLE|style,x,y,width,height,w,(HMENU)(INT_PTR)id,NULL,NULL);
    SendMessageW(child,WM_SETFONT,(WPARAM)font,TRUE);return child;
}
static void controls(void){
    wchar_t text[96];int p=(int)SendMessageW(pitch,TBM_GETPOS,0,0),d=(int)SendMessageW(detail,TBM_GETPOS,0,0),db=-(int)SendMessageW(level,TBM_GETPOS,0,0);
    sm_audio_controls(&audio,p,d,db);
    swprintf(text,96,L"相对音高   ×%.2f",p/1000.);SetWindowTextW(pitch_label,text);
    swprintf(text,96,L"细节起伏   %.0f%%",d/10.);SetWindowTextW(detail_label,text);
    swprintf(text,96,L"输出衰减   %d dB",db);SetWindowTextW(level_label,text);
}
static LRESULT CALLBACK procedure(HWND window,UINT message,WPARAM w,LPARAM l){
    switch(message){
    case WM_CREATE:
        font=CreateFontW(-18,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Microsoft YaHei UI");
        control(window,L"STATIC",L"持续 OSC",0,0,24,18,470,30);
        control(window,L"STATIC",L"sound DNA · 持续生成与音色载入",0,0,24,56,470,28);
        voices=control(window,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,30,24,94,338,240);
        control(window,L"BUTTON",L"载入 DNA",BS_PUSHBUTTON|WS_TABSTOP,31,374,91,120,34);sm_bank_fill(&bank,voices,initial_path);last_voice=(int)SendMessageW(voices,CB_GETCURSEL,0,0);
        pitch_label=control(window,L"STATIC",L"",0,0,24,144,470,28);
        pitch=control(window,TRACKBAR_CLASSW,L"",TBS_HORZ|TBS_NOTICKS|WS_TABSTOP,20,24,177,470,32);
        SendMessageW(pitch,TBM_SETRANGE,TRUE,MAKELPARAM(900,1100));SendMessageW(pitch,TBM_SETPOS,TRUE,1000);
        detail_label=control(window,L"STATIC",L"",0,0,24,224,470,28);
        detail=control(window,TRACKBAR_CLASSW,L"",TBS_HORZ|TBS_NOTICKS|WS_TABSTOP,21,24,257,470,32);
        SendMessageW(detail,TBM_SETRANGE,TRUE,MAKELPARAM(0,1000));SendMessageW(detail,TBM_SETPOS,TRUE,1000);
        level_label=control(window,L"STATIC",L"",0,0,24,304,470,28);
        level=control(window,TRACKBAR_CLASSW,L"",TBS_HORZ|TBS_NOTICKS|WS_TABSTOP,22,24,337,470,32);
        SendMessageW(level,TBM_SETRANGE,TRUE,MAKELPARAM(0,18));
        control(window,L"BUTTON",L"播放／重新开始",BS_PUSHBUTTON|WS_TABSTOP,10,24,392,200,40);
        control(window,L"BUTTON",L"停止",BS_PUSHBUTTON|WS_TABSTOP,11,240,392,110,40);
        status=control(window,L"STATIC",L"已停止",0,0,24,456,470,28);
        control(window,L"STATIC",L"当前只监听 DNA 层",0,0,24,496,490,28);
        controls();SetTimer(window,1,25,NULL);if(smoke.enabled)PostMessageW(window,WM_COMMAND,10,0);return 0;
    case WM_HSCROLL:controls();return 0;
    case WM_CTLCOLORSTATIC:SetBkMode((HDC)w,TRANSPARENT);return (LRESULT)GetSysColorBrush(COLOR_WINDOW);
    case WM_COMMAND:
        if(LOWORD(w)==30&&HIWORD(w)==CBN_SELCHANGE){int selected=(int)SendMessageW(voices,CB_GETCURSEL,0,0);
            if(selected>=0&&(unsigned)selected<bank.count){if(!sm_bank_load(&audio,&model,bank.paths[selected])){SendMessageW(voices,CB_SETCURSEL,last_voice,0);if(smoke.enabled)smoke.passed=0;else MessageBoxW(window,L"模型无效，保留原音色。",L"Sound DNA",MB_OK);}else last_voice=selected;}return 0;}
        if(LOWORD(w)==31){if(sm_bank_choose(&bank,window,voices,&audio,&model)<0)MessageBoxW(window,L"模型无效，保留原音色。",L"Sound DNA",MB_OK);last_voice=(int)SendMessageW(voices,CB_GETCURSEL,0,0);return 0;}
        if(LOWORD(w)==10){if(!sm_audio_start(&audio)){if(smoke.enabled){smoke.passed=0;DestroyWindow(window);}else MessageBoxW(window,L"无法开始监听。",L"Vehicle Sound Lab",MB_OK);}return 0;}
        if(LOWORD(w)==11){sm_audio_stop(&audio);SetWindowTextW(status,L"已停止");return 0;}break;
    case WM_TIMER:{SmStats s=sm_audio_stats(&audio);wchar_t text[128];
        if(s.error[0])swprintf(text,128,L"设备错误：%s",s.error);
        else if(audio.running)swprintf(text,128,L"持续生成   %.1f s    峰值 %.1f dBFS",s.frames/48000.,20*log10(fmax(s.peak,1e-9)));
        else swprintf(text,128,L"已停止");SetWindowTextW(status,text);
        if(smoke.enabled)sm_smoke_tick(&smoke,&audio,window,pitch,detail,level);return 0;}
    case WM_CLOSE:DestroyWindow(window);return 0;
    case WM_DESTROY:
        KillTimer(window,1);sm_audio_stop(&audio);SetWindowTextW(status,L"已停止");
        if(smoke.enabled)sm_smoke_finish(&smoke,&audio,window);
        if(font)DeleteObject(font);PostQuitMessage(0);return 0;
    }return DefWindowProcW(window,message,w,l);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR command,int show){
    int argc,offset=1;wchar_t **args=CommandLineToArgvW(GetCommandLineW(),&argc);char path[2048];MSG msg;HWND window;
    WNDCLASSW klass={0};INITCOMMONCONTROLSEX common={sizeof common,ICC_BAR_CLASSES};(void)previous;(void)command;if(!args)return 2;
    if(argc>1&&!wcscmp(args[1],L"--smoke-test")){smoke.enabled=1;offset=2;}
    if(argc!=offset+1||!WideCharToMultiByte(CP_UTF8,0,args[offset],-1,path,sizeof path,NULL,NULL)){LocalFree(args);return 2;}
    wcscpy_s(initial_path,2048,args[offset]);LocalFree(args);
    if(!sd_profile_load(path,&model))return 2;sm_audio_init(&audio,&model,smoke.enabled);
    if(smoke.enabled&&!sm_smoke_prepare(&smoke,&audio)){sm_audio_destroy(&audio);return 2;}
    InitCommonControlsEx(&common);klass.lpfnWndProc=procedure;klass.hInstance=instance;klass.lpszClassName=L"VslSoundDnaMonitor1";
    klass.hCursor=LoadCursorW(NULL,IDC_ARROW);klass.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);RegisterClassW(&klass);
    window=CreateWindowW(klass.lpszClassName,L"Vehicle Sound Lab · Sound DNA",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,CW_USEDEFAULT,CW_USEDEFAULT,550,580,NULL,NULL,instance,NULL);
    if(!window){sm_audio_destroy(&audio);return 2;}
    if(smoke.enabled){unsigned i;SdProfile *saved=malloc(sizeof *saved);FILE *f;
        if(!saved){sm_audio_destroy(&audio);return 2;}bank_checks=1;
        for(i=0;i<bank.count;++i){bank_checks&=sm_bank_load(&audio,saved,bank.paths[i]);SendMessageW(voices,CB_SETCURSEL,i,0);SendMessageW(window,WM_COMMAND,MAKEWPARAM(30,CBN_SELCHANGE),(LPARAM)voices);bank_checks&=!memcmp(saved,&model,sizeof model);}
        *saved=model;bank_checks&=!sm_bank_load(&audio,&model,L"references/analysis/sound_dna_v1/missing.model")&&!memcmp(saved,&model,sizeof model);
        bank_checks&=sm_bank_load(&audio,&model,initial_path);sm_bank_fill(&bank,voices,initial_path);last_voice=(int)SendMessageW(voices,CB_GETCURSEL,0,0);
        bank_checks&=(unsigned)SendMessageW(voices,CB_GETCOUNT,0,0)==bank.count&&last_voice>=0;free(saved);
        f=fopen("references/analysis/sustain_monitor_v3/bank_checks.json","wb");if(f){fprintf(f,"{\"result\":%s,\"voice_count\":%u,\"failed_load_preserves_profile\":true}\n",bank_checks?"true":"false",bank.count);fclose(f);}else bank_checks=0;
        smoke.passed&=bank_checks;
    }
    ShowWindow(window,smoke.enabled?SW_HIDE:show);UpdateWindow(window);
    while(GetMessageW(&msg,NULL,0,0)>0){if(!IsDialogMessageW(window,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}
    sm_audio_destroy(&audio);return smoke.enabled&&!smoke.passed?3:0;
}

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
static SdProfile model;static LrProfile low_model;static SmAudio audio;static SmSmoke smoke;
static SmBank bank;static HWND voices,mode;static wchar_t initial_path[2048];static int last_voice;
static HWND pitch,detail,rumble,level,pitch_label,detail_label,rumble_label,level_label,status;static HFONT font;
static HWND control(HWND w,const wchar_t *type,const wchar_t *text,DWORD style,int id,int x,int y,int width,int height){
    HWND child=CreateWindowW(type,text,WS_CHILD|WS_VISIBLE|style,x,y,width,height,w,(HMENU)(INT_PTR)id,NULL,NULL);
    SendMessageW(child,WM_SETFONT,(WPARAM)font,TRUE);return child;
}
static HWND slider(HWND w,int id,int y,int lo,int hi,int initial){HWND h=control(w,TRACKBAR_CLASSW,L"",TBS_HORZ|TBS_NOTICKS|WS_TABSTOP,id,24,y,470,32);
    SendMessageW(h,TBM_SETRANGE,TRUE,MAKELPARAM(lo,hi));SendMessageW(h,TBM_SETPOS,TRUE,initial);return h;}
static void controls(void){wchar_t text[96];
    int p=(int)SendMessageW(pitch,TBM_GETPOS,0,0),d=(int)SendMessageW(detail,TBM_GETPOS,0,0),
        a=(int)SendMessageW(rumble,TBM_GETPOS,0,0),db=-(int)SendMessageW(level,TBM_GETPOS,0,0),m=(int)SendMessageW(mode,CB_GETCURSEL,0,0);
    sm_audio_controls(&audio,p,d,db,a,m);
    swprintf(text,96,L"相对音高   ×%.2f",p/1000.);SetWindowTextW(pitch_label,text);
    swprintf(text,96,L"DNA 细节   %.0f%%",d/10.);SetWindowTextW(detail_label,text);
    swprintf(text,96,L"低频轰鸣   %.0f%%",a/10.);SetWindowTextW(rumble_label,text);
    swprintf(text,96,L"输出衰减   %d dB",db);SetWindowTextW(level_label,text);
}
static LRESULT CALLBACK procedure(HWND window,UINT message,WPARAM w,LPARAM l){
    switch(message){
    case WM_CREATE:
        font=CreateFontW(-18,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Microsoft YaHei UI");
        control(window,L"STATIC",L"Sound DNA + 低频轰鸣",0,0,24,18,470,30);
        control(window,L"STATIC",L"轰鸣音色",0,0,24,62,120,26);
        voices=control(window,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,30,24,92,338,240);
        control(window,L"BUTTON",L"载入轰鸣",BS_PUSHBUTTON|WS_TABSTOP,31,374,89,120,34);
        sm_bank_fill(&bank,voices,initial_path);last_voice=(int)SendMessageW(voices,CB_GETCURSEL,0,0);
        mode=control(window,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP,32,24,140,470,160);
        SendMessageW(mode,CB_ADDSTRING,0,(LPARAM)L"DNA + 轰鸣");SendMessageW(mode,CB_ADDSTRING,0,(LPARAM)L"只听 DNA");
        SendMessageW(mode,CB_ADDSTRING,0,(LPARAM)L"只听低频轰鸣");SendMessageW(mode,CB_SETCURSEL,0,0);
        pitch_label=control(window,L"STATIC",L"",0,0,24,190,470,28);pitch=slider(window,20,219,900,1100,1000);
        detail_label=control(window,L"STATIC",L"",0,0,24,264,470,28);detail=slider(window,21,293,0,1000,1000);
        rumble_label=control(window,L"STATIC",L"",0,0,24,338,470,28);rumble=slider(window,23,367,0,1000,600);
        level_label=control(window,L"STATIC",L"",0,0,24,412,470,28);level=slider(window,22,441,0,18,0);
        control(window,L"BUTTON",L"播放／重新开始",BS_PUSHBUTTON|WS_TABSTOP,10,24,496,200,40);
        control(window,L"BUTTON",L"停止",BS_PUSHBUTTON|WS_TABSTOP,11,240,496,110,40);
        status=control(window,L"STATIC",L"已停止",0,0,24,556,470,28);
        control(window,L"STATIC",L"切换轰鸣音色后，点击播放",0,0,24,600,490,28);
        controls();SetTimer(window,1,25,NULL);if(smoke.enabled)PostMessageW(window,WM_COMMAND,10,0);return 0;
    case WM_HSCROLL:controls();return 0;
    case WM_CTLCOLORSTATIC:SetBkMode((HDC)w,TRANSPARENT);return (LRESULT)GetSysColorBrush(COLOR_WINDOW);
    case WM_COMMAND:
        if(LOWORD(w)==32&&HIWORD(w)==CBN_SELCHANGE){controls();return 0;}
        if(LOWORD(w)==30&&HIWORD(w)==CBN_SELCHANGE){int selected=(int)SendMessageW(voices,CB_GETCURSEL,0,0);
            if(selected>=0&&(unsigned)selected<bank.count){if(!sm_bank_load(&audio,&low_model,bank.paths[selected])){
                SendMessageW(voices,CB_SETCURSEL,last_voice,0);if(smoke.enabled)smoke.passed=0;
                else MessageBoxW(window,L"模型无效，保留原轰鸣。",L"Low Rumble",MB_OK);
            }else last_voice=selected;}return 0;}
        if(LOWORD(w)==31){if(sm_bank_choose(&bank,window,voices,&audio,&low_model)<0)MessageBoxW(window,L"模型无效，保留原轰鸣。",L"Low Rumble",MB_OK);
            last_voice=(int)SendMessageW(voices,CB_GETCURSEL,0,0);return 0;}
        if(LOWORD(w)==10){if(!sm_audio_start(&audio)){if(smoke.enabled){smoke.passed=0;DestroyWindow(window);}
            else MessageBoxW(window,L"无法开始监听。",L"Vehicle Sound Lab",MB_OK);}return 0;}
        if(LOWORD(w)==11){sm_audio_stop(&audio);SetWindowTextW(status,L"已停止");return 0;}break;
    case WM_TIMER:{SmStats s=sm_audio_stats(&audio);wchar_t text[128];
        if(s.error[0])swprintf(text,128,L"设备错误：%s",s.error);
        else if(audio.running)swprintf(text,128,L"持续生成   %.1f s    峰值 %.1f dBFS",s.frames/48000.,20*log10(fmax(s.peak,1e-9)));
        else swprintf(text,128,L"已停止");SetWindowTextW(status,text);
        if(smoke.enabled)sm_smoke_tick(&smoke,&audio,window,pitch,detail,level,rumble,mode);return 0;}
    case WM_CLOSE:DestroyWindow(window);return 0;
    case WM_DESTROY:
        KillTimer(window,1);sm_audio_stop(&audio);SetWindowTextW(status,L"已停止");
        if(smoke.enabled)sm_smoke_finish(&smoke,&audio,window);
        if(font)DeleteObject(font);PostQuitMessage(0);return 0;
    }return DefWindowProcW(window,message,w,l);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR command,int show){
    int argc,offset=1;wchar_t **args=CommandLineToArgvW(GetCommandLineW(),&argc);char dna_path[8192],low_path[8192];MSG msg;HWND window;
    WNDCLASSW klass={0};INITCOMMONCONTROLSEX common={sizeof common,ICC_BAR_CLASSES};(void)previous;(void)command;if(!args)return 2;
    if(argc>1&&!wcscmp(args[1],L"--smoke-test")){smoke.enabled=1;offset=2;}
    if(argc!=offset+2||!WideCharToMultiByte(CP_UTF8,0,args[offset],-1,dna_path,sizeof dna_path,NULL,NULL)||
       !WideCharToMultiByte(CP_UTF8,0,args[offset+1],-1,low_path,sizeof low_path,NULL,NULL)){LocalFree(args);return 2;}
    wcscpy_s(initial_path,2048,args[offset+1]);LocalFree(args);
    if(!sd_profile_load(dna_path,&model)||!lr_profile_load(low_path,&low_model))return 2;sm_audio_init(&audio,&model,&low_model,smoke.enabled);
    if(smoke.enabled&&!sm_smoke_prepare(&smoke,&audio)){sm_audio_destroy(&audio);return 2;}
    InitCommonControlsEx(&common);klass.lpfnWndProc=procedure;klass.hInstance=instance;klass.lpszClassName=L"VslDnaRumbleMonitor2";
    klass.hCursor=LoadCursorW(NULL,IDC_ARROW);klass.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);RegisterClassW(&klass);
    window=CreateWindowW(klass.lpszClassName,L"Vehicle Sound Lab · Low Rumble V2",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,CW_USEDEFAULT,CW_USEDEFAULT,550,690,NULL,NULL,instance,NULL);
    if(!window){sm_audio_destroy(&audio);return 2;}
    if(smoke.enabled){unsigned i;LrProfile saved;SdProfile *saved_dna=malloc(sizeof *saved_dna);FILE *f;int passed=1;
        if(!saved_dna){sm_audio_destroy(&audio);return 2;}*saved_dna=model;
        for(i=0;i<bank.count;++i){passed&=sm_bank_load(&audio,&saved,bank.paths[i]);SendMessageW(voices,CB_SETCURSEL,i,0);
            SendMessageW(window,WM_COMMAND,MAKEWPARAM(30,CBN_SELCHANGE),(LPARAM)voices);passed&=!memcmp(&saved,&low_model,sizeof saved)&&!memcmp(saved_dna,&model,sizeof model);}
        saved=low_model;passed&=!sm_bank_load(&audio,&low_model,L"references/analysis/low_rumble_v2/missing.model")&&!memcmp(&saved,&low_model,sizeof saved);
        passed&=sm_bank_load(&audio,&low_model,initial_path);sm_bank_fill(&bank,voices,initial_path);last_voice=(int)SendMessageW(voices,CB_GETCURSEL,0,0);
        passed&=(unsigned)SendMessageW(voices,CB_GETCOUNT,0,0)==bank.count&&last_voice>=0;free(saved_dna);
        f=fopen("references/analysis/sustain_monitor_v4/bank_checks.json","wb");if(f){fprintf(f,"{\"result\":%s,\"voice_count\":%u,\"failed_load_preserves_profile\":true,\"DNA_unchanged\":true}\n",passed?"true":"false",bank.count);fclose(f);}else passed=0;
        smoke.passed&=passed;
    }
    ShowWindow(window,smoke.enabled?SW_HIDE:show);UpdateWindow(window);
    while(GetMessageW(&msg,NULL,0,0)>0){if(!IsDialogMessageW(window,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}
    sm_audio_destroy(&audio);return smoke.enabled&&!smoke.passed?3:0;
}

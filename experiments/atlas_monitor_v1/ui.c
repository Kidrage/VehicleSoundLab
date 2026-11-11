#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <commctrl.h>
#include <shellapi.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include "audio.h"
#include "models.h"
static AmModels models;static SaBank bank;static AmAudio audio;
static HWND slider[8],label[8],status,telemetry,voice,mode,gear;
static HFONT font,heading;static int muted,bank_index;
static const int minimum[]={0,0,700,-24,0,0,0,0},maximum[]={100,100,8500,0,100,100,100,100},initial[]={0,0,1200,-6,70,0,0,0};

static HWND item(HWND owner,const wchar_t *kind,const wchar_t *text,DWORD style,int id,int x,int y,int w,int h) {
    HWND child=CreateWindowW(kind,text,WS_CHILD|WS_VISIBLE|style,x,y,w,h,owner,(HMENU)(INT_PTR)id,NULL,NULL);
    SendMessageW(child,WM_SETFONT,(WPARAM)font,TRUE);return child;
}
static void labels(HWND owner) {
    AdControl c=am_audio_get(&audio);wchar_t text[128];int i;
    swprintf(text,128,L"油门    %.0f%%",c.drive.throttle*100);SetWindowTextW(label[0],text);
    swprintf(text,128,L"制动    %.0f%%",c.drive.brake*100);SetWindowTextW(label[1],text);
    swprintf(text,128,L"台架转速    %.0f RPM",c.drive.rpm);SetWindowTextW(label[2],text);
    swprintf(text,128,L"输出    %.0f dB",20*log10(fmax(1e-12,c.mix.gain/.5)));SetWindowTextW(label[3],text);
    swprintf(text,128,L"空间宽度    %.0f%%",c.mix.width*100);SetWindowTextW(label[4],text);
    swprintf(text,128,L"房间量    %.0f%%",c.mix.room*100);SetWindowTextW(label[5],text);
    swprintf(text,128,L"高频细节    %.0f%%",c.mix.residual_gain*100);SetWindowTextW(label[6],text);
    swprintf(text,128,L"低频分层    %.0f%%",c.mix.body_mix*100);SetWindowTextW(label[7],text);
    for(i=0;i<2;++i)EnableWindow(slider[i],c.drive.mode!=VSL_BENCH);
    EnableWindow(slider[2],c.drive.mode==VSL_BENCH);
    EnableWindow(gear,c.drive.mode!=VSL_BENCH);
    EnableWindow(slider[4],c.mix.spatial);EnableWindow(slider[5],c.mix.spatial);
    SetWindowTextW(GetDlgItem(owner,12),c.drive.ignition?L"熄火":L"点火");
}
static void changed(HWND owner,int index) {
    AdControl c=am_audio_get(&audio);
    int value=(int)SendMessageW(slider[index],TBM_GETPOS,0,0);
    if(index==0)c.drive.throttle=value/100.;
    else if(index==1)c.drive.brake=value/100.;
    else if(index==2)c.drive.rpm=value;
    else if(index==3)c.mix.gain=.5*pow(10,value/20.);
    else if(index==4)c.mix.width=value/100.;
    else if(index==5)c.mix.room=value/100.;
    else if(index==6)c.mix.residual_gain=value/100.;
    else if(index==7)c.mix.body_mix=value/100.;
    am_audio_control(&audio,&c);labels(owner);
}
static int load_bank(int index) {
    AmModels *candidate=malloc(sizeof *candidate);int ok=0;
    if(candidate&&am_models_load(candidate,index)) {
        am_audio_stop(&audio);models=*candidate;
        /* Rebind borrowed pointers to committed storage, never the candidate. */
        if(am_models_bank(&models,&bank)){bank_index=index;ok=1;}
    }
    free(candidate);return ok;
}
static LRESULT CALLBACK procedure(HWND owner,UINT message,WPARAM w,LPARAM l) {
    switch(message) {
    case WM_CREATE: {
        int i;
        font=CreateFontW(-17,0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        heading=CreateFontW(-24,0,0,0,FW_SEMIBOLD,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        SendMessageW(item(owner,L"STATIC",L"DNA 驾驶监听",0,0,24,18,510,36),WM_SETFONT,(WPARAM)heading,TRUE);
        voice=item(owner,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP,40,24,65,510,160);
        SendMessageW(voice,CB_ADDSTRING,0,(LPARAM)L"V10 · 驻车车外四档（实验）");
        SendMessageW(voice,CB_ADDSTRING,0,(LPARAM)L"V10 · 高转车内两档（实验）");SendMessageW(voice,CB_SETCURSEL,0,0);
        mode=item(owner,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP,41,24,108,245,150);
        SendMessageW(mode,CB_ADDSTRING,0,(LPARAM)L"模拟驾驶");SendMessageW(mode,CB_ADDSTRING,0,(LPARAM)L"转速台架");SendMessageW(mode,CB_SETCURSEL,0,0);
        gear=item(owner,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP,42,289,108,245,270);
        SendMessageW(gear,CB_ADDSTRING,0,(LPARAM)L"自动挡 · 运动");SendMessageW(gear,CB_ADDSTRING,0,(LPARAM)L"空挡 N");
        for(i=1;i<=7;++i){wchar_t text[32];swprintf(text,32,L"手动 %d 挡",i);SendMessageW(gear,CB_ADDSTRING,0,(LPARAM)text);}
        SendMessageW(gear,CB_SETCURSEL,0,0);
        telemetry=item(owner,L"STATIC",L"0 RPM    0.0 km/h    N",0,60,24,153,510,32);
        for(i=0;i<8;++i) {
            int y=194+58*i;
            label[i]=item(owner,L"STATIC",L"",0,70+i,24,y,510,25);
            slider[i]=item(owner,TRACKBAR_CLASSW,L"",TBS_HORZ|TBS_NOTICKS|WS_TABSTOP,20+i,24,y+24,510,28);
            SendMessageW(slider[i],TBM_SETRANGEMIN,FALSE,minimum[i]);SendMessageW(slider[i],TBM_SETRANGEMAX,TRUE,maximum[i]);
            SendMessageW(slider[i],TBM_SETPOS,TRUE,initial[i]);
        }
        item(owner,L"BUTTON",L"空间监听",BS_AUTOCHECKBOX|WS_TABSTOP,30,24,670,210,28);
        item(owner,L"BUTTON",L"瞬态层（实验）",BS_AUTOCHECKBOX|WS_TABSTOP,31,276,670,240,28);
        item(owner,L"BUTTON",L"开始／重新监听",BS_PUSHBUTTON|WS_TABSTOP,10,24,712,204,40);
        item(owner,L"BUTTON",L"点火",BS_PUSHBUTTON|WS_TABSTOP,12,244,712,134,40);
        item(owner,L"BUTTON",L"停止",BS_PUSHBUTTON|WS_TABSTOP,11,394,712,140,40);
        status=item(owner,L"STATIC",L"已停止 · 先开始监听，再点火",0,61,24,768,510,30);
        item(owner,L"STATIC",L"实验音色 · 独立进气／机械层待完善",0,0,24,809,510,27);
        labels(owner);SetTimer(owner,1,40,NULL);return 0;
    }
    case WM_HSCROLL: {
        int id=GetDlgCtrlID((HWND)l);if(id>=20&&id<28)changed(owner,id-20);return 0;
    }
    case WM_COMMAND: {
        AdControl c=am_audio_get(&audio);int id=LOWORD(w),notify=HIWORD(w);
        if(id==10) {
            if(!am_audio_start(&audio,muted,0))SetWindowTextW(status,L"无法开始监听");return 0;
        }
        if(id==11){am_audio_stop(&audio);return 0;}
        if(id==12) {
            c.drive.ignition=!c.drive.ignition;
            if(c.drive.ignition)++c.drive.start_id;
            am_audio_control(&audio,&c);labels(owner);return 0;
        }
        if(id==30||id==31) {
            int on=SendMessageW(GetDlgItem(owner,id),BM_GETCHECK,0,0)==BST_CHECKED;
            if(id==30)c.mix.spatial=on;else c.mix.event_gain=on?.3:0;
            am_audio_control(&audio,&c);labels(owner);return 0;
        }
        if(id==40&&notify==CBN_SELCHANGE) {
            int index=(int)SendMessageW(voice,CB_GETCURSEL,0,0);
            if(!load_bank(index))SendMessageW(voice,CB_SETCURSEL,bank_index,0);
            return 0;
        }
        if(id==41&&notify==CBN_SELCHANGE) {
            c.drive.mode=SendMessageW(mode,CB_GETCURSEL,0,0)==1?VSL_BENCH:VSL_PEDALS;
            am_audio_control(&audio,&c);labels(owner);return 0;
        }
        if(id==42&&notify==CBN_SELCHANGE) {
            int selected=(int)SendMessageW(gear,CB_GETCURSEL,0,0);
            c.drive.automatic=selected==0;c.drive.gear=selected==0?1:selected-1;
            am_audio_control(&audio,&c);return 0;
        }
        break;
    }
    case WM_TIMER: {
        WoStats s=wo_stats(&audio.device);AdTelemetry t=am_audio_latest(&audio);wchar_t text[180],g[16];
        if(t.gear>0)swprintf(g,16,L"%d 挡",t.gear);else wcscpy_s(g,16,L"N");
        if(am_audio_get(&audio).drive.mode==VSL_BENCH)swprintf(text,180,L"%.0f RPM    转速台架",t.rpm);
        else swprintf(text,180,L"%.0f RPM    %.1f km/h    %ls",t.rpm,t.speed,g);
        SetWindowTextW(telemetry,text);
        if(s.error[0])SetWindowTextW(status,s.error);
        else if(InterlockedCompareExchange(&audio.device.running,0,0)) {
            swprintf(text,180,L"监听中 · %ls",t.coverage?L"当前音高超出录音锚点区间":L"锚点间过渡");SetWindowTextW(status,text);
        } else SetWindowTextW(status,L"已停止 · 先开始监听，再点火");
        return 0;
    }
    case WM_CTLCOLORSTATIC:SetBkMode((HDC)w,TRANSPARENT);return (LRESULT)GetSysColorBrush(COLOR_WINDOW);
    case WM_CLOSE:DestroyWindow(owner);return 0;
    case WM_DESTROY:
        KillTimer(owner,1);am_audio_stop(&audio);DeleteObject(font);DeleteObject(heading);PostQuitMessage(0);return 0;
    }
    return DefWindowProcW(owner,message,w,l);
}
static int project_directory(void) {
    wchar_t path[4096];int i;
    if(GetFileAttributesW(L"voices/exterior_anchors_v1/index.json")!=INVALID_FILE_ATTRIBUTES)return 1;
    if(!GetModuleFileNameW(NULL,path,4096))return 0;
    for(i=0;i<6;++i) {
        wchar_t *slash=wcsrchr(path,L'\\');if(!slash)return 0;*slash=0;
        if(SetCurrentDirectoryW(path)&&GetFileAttributesW(L"voices/exterior_anchors_v1/index.json")!=INVALID_FILE_ATTRIBUTES)return 1;
    }
    return 0;
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR command,int show) {
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR,&models.residual};
    WNDCLASSW klass={0};INITCOMMONCONTROLSEX common={sizeof common,ICC_BAR_CLASSES};HWND window;MSG message={0};
    int argc,i;wchar_t **args=CommandLineToArgvW(GetCommandLineW(),&argc);(void)previous;(void)command;
    if(!args)return 2;
    for(i=1;i<argc;++i)if(!wcscmp(args[i],L"--muted"))muted=1;else{LocalFree(args);return 2;}
    LocalFree(args);
    if(!project_directory()||!am_models_load(&models,0)||!am_models_bank(&models,&bank))return 2;
    am_audio_init(&audio,&config);InitCommonControlsEx(&common);
    SetProcessDPIAware();klass.lpfnWndProc=procedure;klass.hInstance=instance;klass.lpszClassName=L"VslAtlasMonitor";
    klass.hCursor=LoadCursorW(NULL,IDC_ARROW);klass.hbrBackground=GetSysColorBrush(COLOR_WINDOW);
    if(!RegisterClassW(&klass)){am_audio_destroy(&audio);return 2;}
    window=CreateWindowW(klass.lpszClassName,L"Vehicle Sound Lab · DNA Drive",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,
        CW_USEDEFAULT,CW_USEDEFAULT,580,892,NULL,NULL,instance,NULL);
    if(!window){am_audio_destroy(&audio);return 2;}ShowWindow(window,show);UpdateWindow(window);
    while(GetMessageW(&message,NULL,0,0)>0)if(!IsDialogMessageW(window,&message)){TranslateMessage(&message);DispatchMessageW(&message);}
    am_audio_destroy(&audio);return (int)message.wParam;
}

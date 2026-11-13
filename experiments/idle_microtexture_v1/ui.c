#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <commctrl.h>
#include <shellapi.h>
#include <math.h>
#include <stdio.h>
#include "monitor.h"
#include "win_output/device.h"
enum {ID_PLAY=10,ID_MAIN,ID_DETAIL,ID_GRAIN,ID_LEVEL};
typedef struct {
    FmModels models;FmRender *render;WoDevice device;
    HWND sliders[4],labels[4],status,play;HFONT font;
    volatile LONG main,detail,grain,db;unsigned stopping;double fade;
} App;
static App app;
static int process(void *context,float *out,unsigned frames,int stopping) {
    App *a=context;unsigned n;double main=InterlockedCompareExchange(&a->main,0,0)/100.;
    double detail=InterlockedCompareExchange(&a->detail,0,0)/100.,grain=InterlockedCompareExchange(&a->grain,0,0)/100.;
    double level=pow(10.,InterlockedCompareExchange(&a->db,0,0)/20.);
    if(stopping&&!a->stopping)a->stopping=256;
    for(n=0;n<frames;++n) {
        if(!fm_render_tick(a->render,main,detail,grain,level,out+2*n))return -1;
        if(stopping){if(a->stopping){a->fade=(double)(--a->stopping)/256.;}else a->fade=0;}
        else if(a->fade<1)a->fade=fmin(1,a->fade+1./256.);
        out[2*n]*=(float)a->fade;out[2*n+1]*=(float)a->fade;
    }
    return stopping?1:0;
}
static HWND control(HWND parent,const wchar_t *kind,const wchar_t *text,DWORD style,int x,int y,int w,int h,int id) {
    HWND c=CreateWindowW(kind,text,WS_CHILD|WS_VISIBLE|style,x,y,w,h,parent,(HMENU)(INT_PTR)id,GetModuleHandleW(NULL),NULL);
    SendMessageW(c,WM_SETFONT,(WPARAM)app.font,TRUE);return c;
}
static void labels(void) {
    wchar_t text[80];const wchar_t *names[]={L"主声线",L"细谱量",L"快速颗粒",L"监听电平"};unsigned i;
    for(i=0;i<4;++i) {
        int value=(int)SendMessageW(app.sliders[i],TBM_GETPOS,0,0);
        if(i==3)swprintf(text,80,L"%s    %d dB",names[i],value-24);
        else swprintf(text,80,L"%s    %d%%",names[i],value);
        SetWindowTextW(app.labels[i],text);
        if(i==0)InterlockedExchange(&app.main,value);
        if(i==1)InterlockedExchange(&app.detail,value);
        if(i==2)InterlockedExchange(&app.grain,value);
        if(i==3)InterlockedExchange(&app.db,value-24);
    }
}
static void stop(void){wo_stop(&app.device);fm_render_destroy(app.render);app.render=NULL;SetWindowTextW(app.play,L"开始");}
static LRESULT CALLBACK procedure(HWND window,UINT message,WPARAM w,LPARAM l) {
    switch(message) {
    case WM_CREATE:{unsigned i;app.font=CreateFontW(-19,0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        control(window,L"STATIC",L"固定怠速 · 细节试听",0,26,20,490,28,0);
        control(window,L"STATIC",L"F2 尾排｜转速未标定｜干声",0,26,53,490,26,0);
        for(i=0;i<4;++i){app.labels[i]=control(window,L"STATIC",L"",0,26,102+(int)i*74,490,25,0);
            app.sliders[i]=control(window,TRACKBAR_CLASSW,L"",TBS_HORZ|WS_TABSTOP,22,127+(int)i*74,490,32,ID_MAIN+(int)i);
            SendMessageW(app.sliders[i],TBM_SETRANGE,TRUE,MAKELPARAM(0,i==3?24:100));
            SendMessageW(app.sliders[i],TBM_SETPOS,TRUE,i==2?50:i==3?12:100);}
        labels();app.play=control(window,L"BUTTON",L"开始",BS_PUSHBUTTON|WS_TABSTOP,26,412,110,36,ID_PLAY);
        app.status=control(window,L"STATIC",L"已停止",0,155,417,350,70,0);SetTimer(window,1,200,NULL);return 0;}
    case WM_HSCROLL:labels();return 0;
    case WM_COMMAND:if(LOWORD(w)==ID_PLAY){
        if(app.render)stop();
        else {app.render=fm_render_create(&app.models,149921,app.grain/100.);app.fade=0;app.stopping=0;
            if(!app.render||!wo_start(&app.device,0,0)){stop();SetWindowTextW(app.status,L"无法启动音频");}
            else SetWindowTextW(app.play,L"停止");}return 0;}break;
    case WM_TIMER:{WoStats stats=wo_stats(&app.device);wchar_t text[140];
        if(stats.error[0]){stop();SetWindowTextW(app.status,stats.error);}
        else if(app.render){swprintf(text,140,L"持续生成  %.1f 秒\n峰值 %.3f",stats.frames/48000.,stats.peak);SetWindowTextW(app.status,text);}
        else SetWindowTextW(app.status,L"已停止");return 0;}
    case WM_CLOSE:DestroyWindow(window);return 0;
    case WM_DESTROY:KillTimer(window,1);stop();wo_destroy(&app.device);DeleteObject(app.font);PostQuitMessage(0);return 0;
    }return DefWindowProcW(window,message,w,l);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR command,int show) {
    INITCOMMONCONTROLSEX init={sizeof init,ICC_BAR_CLASSES};WNDCLASSW wc={0};MSG message;HWND window;int count,bytes;LPWSTR *args;char path[2048];
    (void)previous;(void)command;InitCommonControlsEx(&init);args=CommandLineToArgvW(GetCommandLineW(),&count);
    if(!args||count!=2){if(args)LocalFree(args);MessageBoxW(NULL,L"请使用 Launch-Fast-Idle-Study.cmd",L"Vehicle Sound Lab",MB_OK);return 1;}
    bytes=WideCharToMultiByte(CP_UTF8,0,args[1],-1,path,sizeof path,NULL,NULL);LocalFree(args);
    if(!bytes||!fm_models_load(&app.models,path)){MessageBoxW(NULL,L"无法载入固定怠速参数，请先构建。",L"Vehicle Sound Lab",MB_OK);return 2;}
    wo_init(&app.device,process,&app);wc.hInstance=instance;wc.lpfnWndProc=procedure;wc.lpszClassName=L"VslFastIdle1";
    wc.hCursor=LoadCursor(NULL,IDC_ARROW);wc.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);RegisterClassW(&wc);
    window=CreateWindowW(wc.lpszClassName,L"Vehicle Sound Lab · Fast Idle",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,
        CW_USEDEFAULT,CW_USEDEFAULT,558,550,NULL,NULL,instance,NULL);
    if(!window){wo_destroy(&app.device);return 3;}ShowWindow(window,show);UpdateWindow(window);
    while(GetMessageW(&message,NULL,0,0)>0){if(!IsDialogMessageW(window,&message)){TranslateMessage(&message);DispatchMessageW(&message);}}return (int)message.wParam;
}

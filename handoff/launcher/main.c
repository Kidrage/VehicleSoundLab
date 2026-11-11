#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>

typedef struct { const wchar_t *label,*note,*path,*rebuilt,*args; } HubEntry;
static const HubEntry entries[] = {
    {L"驾驶系统 0.20.0", L"完整驾驶控制、分层与录制回放 · 音色仍在研究",
     L"build-v020\\Release\\VehicleSoundLab.exe", L"handoff-build\\bin\\Release\\VehicleSoundLab.exe", NULL},
    {L"驾驶回退 0.15.0", L"较早的稳定功能基线 · 供对照与兼容旧录制",
     L"build-v015\\Release\\VehicleSoundLab.exe", NULL, NULL},
    {L"Sound DNA V1", L"已认可的固定相位方案 · 独立持续声与音色模型",
     L"build-sustain-monitor-v3\\Release\\sustain_osc_monitor.exe", L"handoff-build\\bin\\Release\\VslSoundDna.exe",
     L"\"voices\\dna_bank_v1\\V10 Exterior.model\""},
    {L"新声源联合监听", L"DNA + 相干低频 · 默认直送，空间处理可选",
     L"handoff-build\\bin\\Release\\VslSceneMonitor.exe", L"handoff-build\\bin\\Release\\VslSceneMonitor.exe", NULL},
    {L"低频轰鸣 V2", L"实验对照 · 听评偏风声，保留作为研究证据",
     L"build-sustain-monitor-v4\\Release\\sustain_osc_monitor.exe", L"handoff-build\\bin\\Release\\VslLowRumble.exe",
     L"\"voices\\dna_bank_v1\\V10 Exterior.model\" \"voices\\low_rumble_v2\\A Exterior.model\""},
    {L"交接索引与总图", L"源代码地图、开发记录、回听与复现入口", L"handoff\\index.html", NULL, NULL},
};
#define ENTRY_COUNT (sizeof entries / sizeof entries[0])
#define FIRST_BUTTON 100
#define FALLBACK_ENTRY 1
static wchar_t project_root[4096];
static HWND status;
static HFONT font,heading;
static int use_rebuilt;

static int resolve(wchar_t *full,size_t capacity,const wchar_t *relative){return swprintf(full,capacity,L"%ls\\%ls",project_root,relative)>0;}
static const wchar_t *target(const HubEntry *entry){return use_rebuilt&&entry->rebuilt?entry->rebuilt:entry->path;}
static int exists(const wchar_t *path){wchar_t full[8192];DWORD attr;
    if(!resolve(full,8192,path))return 0;attr=GetFileAttributesW(full);
    return attr!=INVALID_FILE_ATTRIBUTES&&!(attr&FILE_ATTRIBUTE_DIRECTORY);}
static HWND control(HWND owner,const wchar_t *kind,const wchar_t *label,DWORD style,int id,int x,int y,int w,int h,HFONT face){
    HWND child=CreateWindowW(kind,label,WS_CHILD|WS_VISIBLE|style,x,y,w,h,owner,(HMENU)(INT_PTR)id,NULL,NULL);
    if(child)SendMessageW(child,WM_SETFONT,(WPARAM)face,TRUE);return child;}
static void launch(HWND owner,const HubEntry *entry){wchar_t full[8192],message[192];INT_PTR result;
    if(!exists(target(entry))||!resolve(full,8192,target(entry))){SetWindowTextW(status,L"文件缺失。请检查是否完整解压主包。");return;}
    result=(INT_PTR)ShellExecuteW(owner,L"open",full,entry->args,project_root,SW_SHOWNORMAL);
    if(result<=32)swprintf(message,192,L"无法打开 %ls（Windows 返回 %ld）。",entry->label,(long)result);
    else swprintf(message,192,L"已打开：%ls",entry->label);SetWindowTextW(status,message);}
static LRESULT CALLBACK window_proc(HWND owner,UINT message,WPARAM w,LPARAM l){
    switch(message){
    case WM_CREATE:{unsigned i;
        font=CreateFontW(-17,0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        heading=CreateFontW(-28,0,0,0,FW_SEMIBOLD,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        control(owner,L"STATIC",L"Vehicle Sound Lab",0,0,26,20,630,43,heading);
        control(owner,L"STATIC",use_rebuilt?L"交接总入口 · 本机重建产物":L"交接总入口 · 冻结运行产物",0,0,26,68,630,28,font);
        for(i=0;i<ENTRY_COUNT;++i){int y=113+(int)i*59;
            int unavailable=i==FALLBACK_ENTRY&&!exists(target(&entries[i]));
            HWND button=control(owner,L"BUTTON",entries[i].label,WS_TABSTOP|BS_PUSHBUTTON,FIRST_BUTTON+(int)i,26,y,175,39,font);
            if(unavailable)EnableWindow(button,FALSE);
            control(owner,L"STATIC",unavailable?L"此版本需从本地交接包运行":entries[i].note,SS_CENTERIMAGE,0,217,y,445,39,font);}
        status=control(owner,L"STATIC",L"选择一个入口。声音由各窗口手动开始。",0,0,26,128+(int)ENTRY_COUNT*59,640,35,font);return 0;}
    case WM_CTLCOLORSTATIC:SetBkMode((HDC)w,TRANSPARENT);return (LRESULT)GetSysColorBrush(COLOR_WINDOW);
    case WM_COMMAND:{unsigned id=LOWORD(w);if(id>=FIRST_BUTTON&&id<FIRST_BUTTON+ENTRY_COUNT){launch(owner,&entries[id-FIRST_BUTTON]);return 0;}break;}
    case WM_DESTROY:if(font)DeleteObject(font);if(heading)DeleteObject(heading);PostQuitMessage(0);return 0;
    }
    return DefWindowProcW(owner,message,w,l);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR command,int show){
    WNDCLASSW klass={0};HWND window;MSG msg={0};DWORD len;unsigned i;int argc,check=0;
    wchar_t **args=CommandLineToArgvW(GetCommandLineW(),&argc);(void)previous;(void)command;
    if(!args)return 2;
    for(i=1;i<(unsigned)argc;++i){if(!wcscmp(args[i],L"--check"))check=1;
        else if(!wcscmp(args[i],L"--rebuilt"))use_rebuilt=1;else{LocalFree(args);return 2;}}
    LocalFree(args);len=GetCurrentDirectoryW(4096,project_root);if(!len||len>=4096)return 2;
    if(check){for(i=0;i<ENTRY_COUNT;++i)if(!(use_rebuilt&&i==FALLBACK_ENTRY)&&!exists(target(&entries[i])))return 3;
        return exists(L"voices\\dna_bank_v1\\V10 Exterior.model")&&exists(L"voices\\low_rumble_v2\\A Exterior.model")?0:4;}
    klass.lpfnWndProc=window_proc;klass.hInstance=instance;klass.lpszClassName=L"VslHandoffSystem";
    klass.hCursor=LoadCursorW(NULL,IDC_ARROW);klass.hbrBackground=GetSysColorBrush(COLOR_WINDOW);
    if(!RegisterClassW(&klass))return 2;
    window=CreateWindowW(klass.lpszClassName,L"Vehicle Sound Lab · 交接总入口",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,
        CW_USEDEFAULT,CW_USEDEFAULT,704,225+(int)ENTRY_COUNT*59,NULL,NULL,instance,NULL);if(!window)return 2;
    ShowWindow(window,show);UpdateWindow(window);
    while(GetMessageW(&msg,NULL,0,0)>0){if(!IsDialogMessageW(window,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}
    return (int)msg.wParam;
}

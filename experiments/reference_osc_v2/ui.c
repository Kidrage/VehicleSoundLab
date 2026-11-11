#define _CRT_SECURE_NO_WARNINGS
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <commctrl.h>
#include <shellapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include "audio.h"
static RoModel model;static RtTracks tracks;static RtAudio audio;
static HWND pitch,high,pitch_label,high_label,position,play;static HFONT font;
static int smoke,stage,passed=1;static RtAudioStats baseline;
static void label(HWND window,const wchar_t *text,int x,int y,int w,int h) {
    HWND child=CreateWindowW(L"STATIC",text,WS_CHILD|WS_VISIBLE,x,y,w,h,window,NULL,NULL,NULL);SendMessageW(child,WM_SETFONT,(WPARAM)font,TRUE);
}
static HWND control(HWND window,const wchar_t *type,const wchar_t *text,DWORD style,int id,int x,int y,int w,int h) {
    HWND child=CreateWindowW(type,text,WS_CHILD|WS_VISIBLE|style,x,y,w,h,window,(HMENU)(INT_PTR)id,NULL,NULL);SendMessageW(child,WM_SETFONT,(WPARAM)font,TRUE);return child;
}
static void controls(void) {
    wchar_t text[80];int p=(int)SendMessageW(pitch,TBM_GETPOS,0,0),h=(int)SendMessageW(high,TBM_GETPOS,0,0);
    rt_audio_controls(&audio,p,h);swprintf(text,80,L"音高  ×%.2f",p/1000.);SetWindowTextW(pitch_label,text);
    swprintf(text,80,L"高频补充  %d%%",h);SetWindowTextW(high_label,text);
}
static void screenshot(HWND window) {
    RECT r;HDC dc,memory;HBITMAP bitmap,old;BITMAPINFO info={0};BITMAPFILEHEADER header={0};unsigned char *pixels;FILE *f;int width,height;
    GetWindowRect(window,&r);width=r.right-r.left;height=r.bottom-r.top;r.left=r.top=0;r.right=width;r.bottom=height;
    dc=GetWindowDC(window);memory=CreateCompatibleDC(dc);bitmap=CreateCompatibleBitmap(dc,width,height);old=SelectObject(memory,bitmap);
    /* Render this app's hidden smoke window and native child controls directly.
       PrintWindow on an unshown window can return an untouched black bitmap. */
    FillRect(memory,&r,GetSysColorBrush(COLOR_WINDOW));
    SendMessageW(window,WM_PRINT,(WPARAM)memory,PRF_NONCLIENT|PRF_CLIENT|PRF_ERASEBKGND|PRF_CHILDREN);
    info.bmiHeader.biSize=sizeof info.bmiHeader;info.bmiHeader.biWidth=width;info.bmiHeader.biHeight=-height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
    pixels=malloc((size_t)width*height*4);SelectObject(memory,old);
    if(pixels&&GetDIBits(dc,bitmap,0,(UINT)height,pixels,&info,DIB_RGB_COLORS)){
        header.bfType=0x4d42;header.bfOffBits=sizeof header+sizeof info.bmiHeader;header.bfSize=header.bfOffBits+width*height*4;
        f=fopen("references/analysis/reference_osc_v2/native_preview.bmp","wb");if(f){fwrite(&header,sizeof header,1,f);fwrite(&info.bmiHeader,sizeof info.bmiHeader,1,f);fwrite(pixels,4,(size_t)width*height,f);fclose(f);}}
    free(pixels);DeleteObject(bitmap);DeleteDC(memory);ReleaseDC(window,dc);
}
static void report(RtAudioStats live,int ui_controls) {
    FILE *f=fopen("references/analysis/reference_osc_v2/native_preview.json","wb");if(!f){passed=0;return;}
    passed=baseline.opened&&!baseline.error[0]&&baseline.frames==model.frames&&baseline.queue_empty==0&&
        baseline.device_seconds>5.9&&baseline.device_seconds/baseline.wall_seconds>.95&&baseline.device_seconds/baseline.wall_seconds<1.03&&
        baseline.render_ms_total/baseline.blocks<512000./model.rate&&ui_controls&&live.max_pitch>1.09&&live.max_high>.49&&!live.error[0];
    fprintf(f,"{\n  \"result\":\"%s\",\n  \"device_muted\":true,\n  \"frames\":%" PRIu64 ",\n  \"raw_float_hash\":\"%016" PRIx64 "\",\n  \"device_seconds\":%.9f,\n  \"wall_seconds\":%.9f,\n  \"queue_empty\":%u,\n  \"blocks\":%u,\n  \"render_ms_mean\":%.9f,\n  \"render_ms_max\":%.9f,\n  \"ui_controls\":%s,\n  \"live_max_pitch\":%.9f,\n  \"live_max_high\":%.9f\n}\n",
        passed?"pass":"fail",baseline.frames,baseline.raw_hash,baseline.device_seconds,baseline.wall_seconds,baseline.queue_empty,baseline.blocks,
        baseline.blocks?baseline.render_ms_total/baseline.blocks:0,baseline.render_ms_max,ui_controls?"true":"false",live.max_pitch,live.max_high);fclose(f);
}
static LRESULT CALLBACK procedure(HWND window,UINT message,WPARAM w,LPARAM l) {
    switch(message){
    case WM_CREATE:
        font=CreateFontW(-18,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Microsoft YaHei UI");
        label(window,L"旧 64 OSC · 实时参数试听",24,20,460,30);
        label(window,L"六秒声纹片段；高频差异在 2.6 秒后。",24,58,470,28);
        pitch_label=control(window,L"STATIC",L"音高 ×1.00",0,0,24,106,460,28);
        pitch=control(window,TRACKBAR_CLASSW,L"",TBS_HORZ|TBS_NOTICKS|WS_TABSTOP,20,24,138,460,32);
        SendMessageW(pitch,TBM_SETRANGE,TRUE,MAKELPARAM(900,1100));SendMessageW(pitch,TBM_SETPOS,TRUE,1000);
        high_label=control(window,L"STATIC",L"高频补充 0%",0,0,24,186,460,28);
        high=control(window,TRACKBAR_CLASSW,L"",TBS_HORZ|TBS_NOTICKS|WS_TABSTOP,21,24,218,460,32);
        SendMessageW(high,TBM_SETRANGE,TRUE,MAKELPARAM(0,50));
        play=control(window,L"BUTTON",L"播放 / 重新开始",BS_PUSHBUTTON|WS_TABSTOP,10,24,278,190,38);
        control(window,L"BUTTON",L"停止",BS_PUSHBUTTON|WS_TABSTOP,11,230,278,100,38);
        position=control(window,L"STATIC",L"0.00 / 6.00 s",0,0,348,286,140,30);
        label(window,L"相对音高控制；尚非任意 RPM / 负载的驾驶音色。",24,340,480,28);
        controls();SetTimer(window,1,25,NULL);if(smoke)PostMessageW(window,WM_COMMAND,10,0);return 0;
    case WM_HSCROLL:controls();return 0;
    case WM_CTLCOLORSTATIC:SetBkMode((HDC)w,TRANSPARENT);return (LRESULT)GetSysColorBrush(COLOR_WINDOW);
    case WM_COMMAND:
        if(LOWORD(w)==10){if(!rt_audio_start(&audio))MessageBoxW(window,L"无法开始 C 声纹试听。",L"Vehicle Sound Lab",MB_OK);if(smoke&&stage==0)stage=1;return 0;}
        if(LOWORD(w)==11){rt_audio_stop(&audio);return 0;}break;
    case WM_TIMER:{
        RtAudioStats s=rt_audio_stats(&audio);wchar_t text[80];swprintf(text,80,L"%.2f / 6.00 s",s.frames/(double)model.rate);SetWindowTextW(position,text);
        if(smoke&&stage==1&&!audio.running){
            baseline=s;stage=2;SendMessageW(pitch,TBM_SETPOS,TRUE,1000);SendMessageW(high,TBM_SETPOS,TRUE,0);controls();
            if(!rt_audio_start(&audio)){passed=0;DestroyWindow(window);break;}
            SendMessageW(pitch,TBM_SETPOS,TRUE,1100);SendMessageW(window,WM_HSCROLL,TB_THUMBPOSITION,(LPARAM)pitch);
            SendMessageW(high,TBM_SETPOS,TRUE,50);SendMessageW(window,WM_HSCROLL,TB_THUMBPOSITION,(LPARAM)high);
        }else if(smoke&&stage==2&&(s.frames>model.rate/2||!audio.running)){
            int valid=audio.pitch_milli==1100&&audio.high_percent==50;rt_audio_stop(&audio);s=rt_audio_stats(&audio);
            report(s,valid);SendMessageW(pitch,TBM_SETPOS,TRUE,1000);SendMessageW(high,TBM_SETPOS,TRUE,0);controls();
            SetWindowTextW(position,L"0.00 / 6.00 s");UpdateWindow(window);screenshot(window);stage=3;DestroyWindow(window);
        }else if(!smoke&&!audio.running&&s.error[0]){SetWindowTextW(position,L"设备错误");}
        return 0;}
    case WM_CLOSE:DestroyWindow(window);return 0;
    case WM_DESTROY:KillTimer(window,1);rt_audio_stop(&audio);if(font)DeleteObject(font);PostQuitMessage(0);return 0;
    }return DefWindowProcW(window,message,w,l);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR command,int show) {
    int argc,offset=1;wchar_t **args=CommandLineToArgvW(GetCommandLineW(),&argc),*gain_end;char path[2048],id_path[2048];double gain;MSG msg;
    WNDCLASSW klass={0};HWND window;INITCOMMONCONTROLSEX common={sizeof common,ICC_BAR_CLASSES};
    (void)previous;(void)command;if(!args)return 2;
    if(argc>1&&!wcscmp(args[1],L"--smoke-test")){smoke=1;offset=2;}
    if(argc!=offset+3){LocalFree(args);return 2;}
    if(!WideCharToMultiByte(CP_UTF8,0,args[offset],-1,path,sizeof path,NULL,NULL)||!WideCharToMultiByte(CP_UTF8,0,args[offset+1],-1,id_path,sizeof id_path,NULL,NULL)){LocalFree(args);return 2;}
    gain=wcstod(args[offset+2],&gain_end);if(gain_end==args[offset+2]||*gain_end){LocalFree(args);return 2;}LocalFree(args);
    if(!(gain>0&&gain<=1)||!ro_model_load(path,&model)||!rt_tracks_load(id_path,&model,&tracks))return 2;
    rt_audio_init(&audio,&model,&tracks,gain,smoke);InitCommonControlsEx(&common);
    klass.lpfnWndProc=procedure;klass.hInstance=instance;klass.lpszClassName=L"VslAccepted64Preview";klass.hCursor=LoadCursorW(NULL,IDC_ARROW);klass.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);
    RegisterClassW(&klass);window=CreateWindowW(klass.lpszClassName,L"Vehicle Sound Lab · 64 OSC",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,CW_USEDEFAULT,CW_USEDEFAULT,540,425,NULL,NULL,instance,NULL);
    if(!window){rt_audio_destroy(&audio);rt_tracks_free(&tracks);ro_model_free(&model);return 2;}
    ShowWindow(window,smoke?SW_HIDE:show);UpdateWindow(window);
    while(GetMessageW(&msg,NULL,0,0)>0){if(!IsDialogMessageW(window,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}
    rt_audio_destroy(&audio);rt_tracks_free(&tracks);ro_model_free(&model);return passed?0:3;
}

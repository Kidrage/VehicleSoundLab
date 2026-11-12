#define _CRT_SECURE_NO_WARNINGS
#include "ui_checks.h"
#include <commctrl.h>
#include <stdio.h>
#include <math.h>
#define CHECK(x) do{++checks;if(!(x)){line=__LINE__;goto done;}}while(0)
/* Own-program controls/window only. No external desktop automation. */
static int capture(HWND w,const wchar_t *path) {
    RECT r;HDC dc,m;HBITMAP bitmap,old;BITMAPINFO info={0};BITMAPFILEHEADER header={0};void *pixels;FILE *f;int ok=0;DWORD bytes;
    GetWindowRect(w,&r);dc=GetWindowDC(w);m=CreateCompatibleDC(dc);info.bmiHeader.biSize=sizeof info.bmiHeader;
    info.bmiHeader.biWidth=r.right-r.left;info.bmiHeader.biHeight=r.top-r.bottom;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;
    bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&pixels,NULL,0);if(!bitmap){DeleteDC(m);ReleaseDC(w,dc);return 0;}
    old=SelectObject(m,bitmap);ShowWindow(w,SW_SHOWNOACTIVATE);
    RedrawWindow(w,NULL,NULL,RDW_INVALIDATE|RDW_ERASE|RDW_FRAME|RDW_ALLCHILDREN|RDW_UPDATENOW);
    if(!PrintWindow(w,m,0))goto done;
    bytes=(DWORD)(info.bmiHeader.biWidth*-info.bmiHeader.biHeight*4);header.bfType=0x4d42;header.bfOffBits=sizeof header+sizeof info.bmiHeader;header.bfSize=header.bfOffBits+bytes;
    f=_wfopen(path,L"wb");if(!f)goto done;ok=fwrite(&header,sizeof header,1,f)==1&&fwrite(&info.bmiHeader,sizeof info.bmiHeader,1,f)==1&&fwrite(pixels,bytes,1,f)==1;if(fclose(f))ok=0;
done:SelectObject(m,old);DeleteObject(bitmap);DeleteDC(m);ReleaseDC(w,dc);return ok;
}
int am_resonant_ui_check(HWND w,AmAudio *a,const wchar_t *path) {
    unsigned checks=0;int line=0,ok=0;AdControl c=am_audio_get(a);FILE *f;wchar_t bmp[4096];HWND detail=GetDlgItem(w,26),mode=GetDlgItem(w,41);
    CHECK(a->config.resonant_bank&&!a->config.residual_bank&&a->config.scene_mode==AD_SCENE_STEREO_BED);
    CHECK(!a->device.running&&!c.drive.ignition&&c.drive.mode==VSL_BENCH&&c.mix.resonant_gain==0&&c.mix.room==0);
    CHECK(IsWindowEnabled(detail)&&!IsWindowEnabled(GetDlgItem(w,40)));
    for(int i=0;i<=100;i+=50) {
        SendMessageW(detail,TBM_SETPOS,TRUE,i);SendMessageW(w,WM_HSCROLL,TB_THUMBPOSITION,(LPARAM)detail);
        c=am_audio_get(a);CHECK(c.mix.resonant_gain==i/100.&&c.mix.residual_gain==0);
    }
    SendMessageW(mode,CB_SETCURSEL,0,0);SendMessageW(w,WM_COMMAND,MAKEWPARAM(41,CBN_SELCHANGE),(LPARAM)mode);
    CHECK(am_audio_get(a).drive.mode==VSL_PEDALS&&IsWindowEnabled(GetDlgItem(w,20)));
    SendMessageW(mode,CB_SETCURSEL,1,0);SendMessageW(w,WM_COMMAND,MAKEWPARAM(41,CBN_SELCHANGE),(LPARAM)mode);
    CHECK(am_audio_get(a).drive.mode==VSL_BENCH&&IsWindowEnabled(GetDlgItem(w,22)));
    SendMessageW(w,WM_COMMAND,12,0);CHECK(am_audio_get(a).drive.ignition==1);SendMessageW(w,WM_COMMAND,12,0);
    CHECK(am_audio_get(a).drive.ignition==0&&!a->device.running);
    swprintf(bmp,4096,L"%ls.bmp",path);CHECK(capture(w,bmp));ok=1;
done:
    f=_wfopen(path,L"wb");if(!f)return 0;
    fprintf(f,"{\"result\":\"%s\",\"checks\":%u,\"failed_line\":%d,\"own_program_controls\":true,\"audio_started\":false,\"manual_mouse_verified\":false}\n",ok?"pass":"fail",checks,line);
    if(fclose(f))ok=0;return ok;
}

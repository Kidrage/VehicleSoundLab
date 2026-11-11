#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <windowsx.h>
#include <commctrl.h>
#include <commdlg.h>
#include <mmsystem.h>
#include <shellapi.h>
#include <math.h>
#include <stdio.h>
#include "audio_device.h"
#include "io/render_session.h"
#include "io/wav.h"
#include "drive/drive.h"
#include "preset.h"
#include "drive_panel.h"
#include "tuning.h"
#include "takes.h"
#include "take_smoke.h"
#include "driver_keys.h"
#include "ui_input_check.h"
#include "version.h"
#include <stdlib.h>

enum { ID_PLAY=100,ID_EXPORT,ID_REPLAY,ID_SAVE,ID_LOAD,ID_DNA,ID_IR,ID_PROFILE,ID_PURE,ID_DRIVE,ID_CLEAR,ID_CABIN,ID_TUNING,ID_TAKE_NEW,ID_TAKE_SAVE,ID_TAKE_PLAY };
static VslAudio audio;
static VslTakes takes;
static int replaying;
static VslParams before_replay;
static VslParams params;
static HWND window,profile,pure,drive,cabin,play,sliders[8];
static HFONT font,large,title_font,small_font;
static HBRUSH bg,card;
static wchar_t workspace[MAX_PATH],last_export[MAX_PATH],dna_file[MAX_PATH],ir_file[MAX_PATH];
static wchar_t status_text[256]=L"Ready · muted on launch · reference fitting pending";
static int smoke_fuel_controls,smoke_fuel_preset,smoke_control_isolation;
static int smoke_mechanical_control,smoke_mechanical_preset;
static int smoke_mechanical_legacy_preset;
static int smoke_combustion_control,smoke_combustion_preset,smoke_combustion_legacy_preset;
static int smoke_vehicle_ok;
static int smoke_coupling_ok;
static int smoke_propagation_control,smoke_propagation_preset,smoke_propagation_legacy;
static int smoke_propagation_active;
static int smoke_character_control,smoke_character_preset,smoke_character_legacy,smoke_character_active;
static int smoke_response_control,smoke_response_preset,smoke_response_legacy,smoke_response_active;
static int smoke_color_control,smoke_color_preset,smoke_color_legacy,smoke_color_active;
static int smoke_pulse_control,smoke_pulse_preset,smoke_pulse_legacy,smoke_pulse_active;
static const wchar_t *names[8]={L"THROTTLE",L"BRAKE",L"DNA",L"BODY / PAD",L"NVH / AIR",L"WIDTH",L"SPACE / IR",L"OUTPUT"};
static const int xs[8]={28,480,28,330,632,28,330,632};
static const int ys[8]={294,294,399,399,399,499,499,499};
static const int widths[8]={422,422,270,270,270,270,270,270};
static int preview;
static int smoke_mode,smoke_tick,smoke_audio_ok,capture_preview;
static int ui_input_mode;
static VslUiInputCheck ui_input_check;
static int smoke_running_ok,smoke_shift_ok,smoke_shutdown_ok,key_throttle,key_brake;
static unsigned smoke_shifts_before;static int smoke_requested_gear;
static const wchar_t *diagnostic_path(const wchar_t *name) {
    static wchar_t path[MAX_PATH];
    swprintf(path,MAX_PATH,L"%s\\renders\\%s\\%s",workspace,VSL_DIAGNOSTIC_FOLDER_W,name);return path;
}

static HWND capture_parent;
static BOOL CALLBACK capture_child(HWND child,LPARAM context) {
    RECT r; HDC dc=(HDC)context; POINT previous;
    if(!(GetWindowLongPtrW(child,GWL_STYLE)&WS_VISIBLE) || GetParent(child)!=capture_parent)return TRUE;
    GetWindowRect(child,&r); MapWindowPoints(HWND_DESKTOP,capture_parent,(POINT*)&r,2);
    SetViewportOrgEx(dc,r.left,r.top,&previous);
    SendMessageW(child,WM_PRINT,(WPARAM)dc,PRF_CLIENT|PRF_CHILDREN|PRF_ERASEBKGND);
    /* Hidden owner-draw combos omit their selection in WM_PRINT. Exercise
       the same parent renderer with the real selection and native item rect. */
    {
        wchar_t cls[32];COMBOBOXINFO info={sizeof info};
        GetClassNameW(child,cls,32);
        if(!wcscmp(cls,L"ComboBox")&&(GetWindowLongPtrW(child,GWL_STYLE)&CBS_OWNERDRAWFIXED)&&GetComboBoxInfo(child,&info)) {
            int selected=(int)SendMessageW(child,CB_GETCURSEL,0,0);
            if(selected!=CB_ERR) {
                DRAWITEMSTRUCT item={0};item.CtlType=ODT_COMBOBOX;item.CtlID=GetDlgCtrlID(child);
                item.itemID=(UINT)selected;item.itemAction=ODA_DRAWENTIRE;item.itemState=ODS_COMBOBOXEDIT;
                item.hwndItem=child;item.hDC=dc;item.rcItem=info.rcItem;
                SendMessageW(capture_parent,WM_DRAWITEM,item.CtlID,(LPARAM)&item);
            }
        }
    }
    SetViewportOrgEx(dc,previous.x,previous.y,NULL); return TRUE;
}

/* An in-process diagnostic harness tests this application's own controls,
   renderer and waveOut lifecycle; it does not automate other desktop apps. */
static void diagnostic_capture_window(HWND target,const wchar_t *path) {
    RECT r; HDC dc=GetDC(target),mem=CreateCompatibleDC(dc); HBITMAP image,old;
    BITMAPINFO info={0}; BITMAPFILEHEADER header={0}; FILE*f; void*bits;
    DWORD bytes;
    GetClientRect(target,&r);capture_parent=target;
    info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER); info.bmiHeader.biWidth=r.right;
    info.bmiHeader.biHeight=-r.bottom; info.bmiHeader.biPlanes=1; info.bmiHeader.biBitCount=32;
    image=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&bits,NULL,0); old=SelectObject(mem,image);
    if(IsWindowVisible(target))BitBlt(mem,0,0,r.right,r.bottom,dc,0,0,SRCCOPY);
    else {
        FillRect(mem,&r,GetSysColorBrush(COLOR_BTNFACE));
        SendMessageW(target,WM_PRINTCLIENT,(WPARAM)mem,PRF_CLIENT);
        EnumChildWindows(target,capture_child,(LPARAM)mem);
    }
    bytes=(DWORD)(r.right*r.bottom*4); header.bfType=0x4d42;
    header.bfOffBits=sizeof header+sizeof(BITMAPINFOHEADER); header.bfSize=header.bfOffBits+bytes;
    f=_wfopen(path,L"wb");
    if(f) { fwrite(&header,sizeof header,1,f); fwrite(&info.bmiHeader,sizeof(BITMAPINFOHEADER),1,f); fwrite(bits,1,bytes,f); fclose(f); }
    SelectObject(mem,old); DeleteObject(image); DeleteDC(mem); ReleaseDC(target,dc);
}
static void diagnostic_capture(const wchar_t *path) { diagnostic_capture_window(window,path); }
static void input_capture(const wchar_t *name) { diagnostic_capture(diagnostic_path(name)); }

static void utf8(const wchar_t*w,char*b,int n) { WideCharToMultiByte(CP_UTF8,0,w,-1,b,n,NULL,NULL); }
static void text_at(HDC dc,int x,int y,const wchar_t*s,HFONT f,COLORREF color) {
    SelectObject(dc,f); SetTextColor(dc,color); SetBkMode(dc,TRANSPARENT); TextOutW(dc,x,y,s,(int)wcslen(s));
}
static HWND control(const wchar_t*cls,const wchar_t*txt,DWORD style,int x,int y,int w,int h,int id) {
    if(!wcscmp(cls,L"BUTTON") && !(style&BS_AUTOCHECKBOX))style=(style&~0xf)|BS_OWNERDRAW;
    HWND c=CreateWindowExW(0,cls,txt,WS_CHILD|WS_VISIBLE|WS_TABSTOP|style,x,y,w,h,window,(HMENU)(INT_PTR)id,GetModuleHandleW(NULL),NULL);
    SendMessageW(c,WM_SETFONT,(WPARAM)font,TRUE); return c;
}
static void slider_values(void) {
    int bench=params.drive_mode==VSL_BENCH;
    double values[8]={bench?params.rpm/10000:params.throttle,bench?(params.load+1)*.5:params.brake,params.dna,params.pad,params.noise,params.width,params.space,params.master};
    int i;
    for(i=0;i<8;++i)SendMessageW(sliders[i],TBM_SETPOS,TRUE,(LPARAM)(values[i]*1000));
    SendMessageW(profile,CB_SETCURSEL,params.profile,0); Button_SetCheck(pure,params.pure_osc);
    SendMessageW(drive,CB_SETCURSEL,params.drive_mode,0);Button_SetCheck(cabin,params.perspective>.5);
    vsl_drive_panel_sync(&params);
    vsl_tuning_sync();
    InvalidateRect(window,NULL,FALSE);
}
static void publish(void) {
    int scripted=params.drive_mode==VSL_AUTODRIVE;
    if(replaying)return;
    EnableWindow(sliders[0],!scripted);EnableWindow(sliders[1],!scripted);
    vsl_audio_params(&audio,&params,scripted);
    InvalidateRect(window,NULL,FALSE);
}
static int load_assets(void);
static BOOL CALLBACK take_control(HWND child,LPARAM enabled) {
    int id=GetDlgCtrlID(child);
    if(id!=ID_PLAY)EnableWindow(child,(BOOL)enabled);
    return TRUE;
}
static void take_controls(int enabled) {
    EnumChildWindows(window,take_control,enabled);vsl_tuning_enable(enabled);
    if(enabled)publish();
}
static void stop(void) {
    PlaySoundW(NULL,NULL,0); preview=0; vsl_audio_stop(&audio); SetWindowTextW(play,L"▶  Listen");
    if(audio.take_mode==1) {
        if(vsl_takes_preserve(&takes,workspace))wcscpy(status_text,L"Take saved in performances · ready to replay");
        else wcscpy(status_text,L"Take save failed · retained in memory; use Save take before closing");
    }
    audio.take_mode=0;
    SetWindowTextW(GetDlgItem(window,ID_TAKE_NEW),L"New take");
    if(replaying) {
        replaying=0;params=before_replay;
        params.ignition=0;params.start_id=0;params.throttle=params.brake=0;key_throttle=key_brake=0;
        load_assets();slider_values();take_controls(1);
    }
}
static int choose(wchar_t*path,const wchar_t*filter,int save,const wchar_t*ext) {
    OPENFILENAMEW ofn={0}; ofn.lStructSize=sizeof ofn; ofn.hwndOwner=window; ofn.lpstrFilter=filter;
    ofn.lpstrFile=path; ofn.nMaxFile=MAX_PATH; ofn.lpstrInitialDir=workspace; ofn.lpstrDefExt=ext;
    ofn.Flags=OFN_EXPLORER|OFN_PATHMUSTEXIST|(save?OFN_OVERWRITEPROMPT:OFN_FILEMUSTEXIST);
    return save?GetSaveFileNameW(&ofn):GetOpenFileNameW(&ofn);
}
static void save_state(const wchar_t*file) {
    vsl_preset_save(file,&params,dna_file,ir_file);
}
static int load_assets(void) {
    char path[MAX_PATH*4];
    vsl_init(audio.engine,48000,48271);
    if(dna_file[0]) { utf8(dna_file,path,sizeof path); if(!vsl_load_dna(audio.engine,path))return 0; }
    if(ir_file[0]) {
        unsigned n,sr,i; float *data; int ok;
        utf8(ir_file,path,sizeof path); data=vsl_wav_read(path,&n,&sr);
        if(!data || n>VSL_MAX_IR || sr!=48000) { free(data); return 0; }
        for(i=0;i<n;++i)data[i]=.5f*(data[2*i]+data[2*i+1]);
        ok=vsl_set_ir(audio.engine,data,n,sr); free(data); if(!ok)return 0;
    }
    vsl_set_params(audio.engine,&params);audio.state=audio.engine->drive;return 1;
}
static void command(int id) {
    wchar_t file[MAX_PATH]=L""; char path[MAX_PATH*4],dna[MAX_PATH*4],ir[MAX_PATH*4];
    int gear;
    if(replaying&&id!=ID_PLAY)return;
    EnterCriticalSection(&audio.lock);gear=audio.running?audio.state.gear:audio.engine->drive.gear;LeaveCriticalSection(&audio.lock);
    if(id==ID_TAKE_NEW) {
        int recording=audio.take_mode==1;
        stop();if(recording)return;
        if(!vsl_takes_preserve(&takes,workspace))return;
        params.ignition=0;params.start_id=0;params.throttle=params.brake=0;key_throttle=key_brake=0;
        if(params.drive_mode==VSL_BENCH)params.drive_mode=VSL_PEDALS;
        if(!load_assets()||!vsl_takes_new(&takes,&audio)) { wcscpy(status_text,L"Could not initialize a fresh take");return; }
        slider_values();publish();
        if(vsl_audio_start(&audio)) {
            SetWindowTextW(GetDlgItem(window,ID_TAKE_NEW),L"Stop take");SetWindowTextW(play,L"■  Stop take");
            wcscpy(status_text,L"Recording · press Start, then drive · Stop saves to performances");
        } else { audio.take_mode=0;wcscpy(status_text,L"Audio device could not start"); }
    } else if(id==ID_TAKE_SAVE) {
        stop();
        if(takes.path[0])wcscpy(file,takes.path);else swprintf(file,MAX_PATH,L"%s\\performances\\driving.vsltake",workspace);
        if(!takes.take.frames) { wcscpy(status_text,L"Use New take and drive before saving");return; }
        if(choose(file,L"Driving take\0*.vsltake\0\0",1,L"vsltake"))
            wcscpy(status_text,vsl_takes_save(&takes,file)?L"Driving take saved with embedded DNA and IR":L"Save failed · take retained in memory");
    } else if(id==ID_TAKE_PLAY) {
        stop();if(!vsl_takes_preserve(&takes,workspace))return;
        if(takes.path[0])wcscpy(file,takes.path);
        if(choose(file,L"Driving take\0*.vsltake\0\0",0,L"vsltake")) {
            before_replay=params;
            if(!vsl_takes_play(&takes,&audio,file)) { wcscpy(status_text,L"Invalid take or incompatible DSP version");return; }
            replaying=1;take_controls(0);
            if(vsl_audio_start(&audio)) {
                SetWindowTextW(play,L"■  Stop replay");wcscpy(status_text,L"Replaying recorded inputs · driving and sound controls locked");
            } else { stop();wcscpy(status_text,L"Audio device could not start"); }
        }
    } else if(vsl_drive_panel_command(id,&params,gear)) {
        if(id==ID_IGNITION && !params.ignition && !audio.running) { load_assets();audio.state=audio.engine->drive; }
        publish();
        if(id==ID_START && !audio.running) { stop();publish();vsl_audio_start(&audio);SetWindowTextW(play,L"■  Stop monitor"); }
        wcscpy(status_text,L"W / S: throttle / brake · Q / E: gears · ignition off stops the engine");
    } else if(id==ID_TUNING) { vsl_tuning_show(window,font,&params);
    } else if(id==ID_CABIN) { params.perspective=Button_GetCheck(cabin)==BST_CHECKED;publish();
    } else if(id==ID_PLAY) {
        if(audio.running || preview || replaying || audio.take_mode==1) { int take=audio.take_mode;stop();if(!take)wcscpy(status_text,L"Stopped"); }
        else {
            publish();
            if(vsl_audio_start(&audio)) { SetWindowTextW(play,L"■  Stop"); wcscpy(status_text,L"Listening · 48 kHz · stereo"); }
            else wcscpy(status_text,L"Audio device could not start");
        }
    } else if(id==ID_PROFILE) {
        stop();params.profile=(int)SendMessageW(profile,CB_GETCURSEL,0,0);params.rpm=vsl_profile(params.profile)->idle_rpm;
        params.ignition=0;params.start_id=0;load_assets();slider_values();publish();
    } else if(id==ID_PURE || id==ID_DRIVE) {
        params.pure_osc=Button_GetCheck(pure)==BST_CHECKED;params.drive_mode=(int)SendMessageW(drive,CB_GETCURSEL,0,0);
        params.throttle=params.brake=0;slider_values();publish();
    } else if(id==ID_EXPORT) {
        wcscpy(file,L"v10_drive.wav");
        if(choose(file,L"WAV audio\0*.wav\0\0",1,L"wav")) {
            stop(); utf8(file,path,sizeof path); utf8(dna_file,dna,sizeof dna); utf8(ir_file,ir,sizeof ir);
            SetCursor(LoadCursor(NULL,IDC_WAIT));
            if(vsl_render_file(path,&params,30,params.drive_mode==VSL_AUTODRIVE,dna,ir)) {
                wchar_t sidecar[MAX_PATH+8]; wcscpy(last_export,file); swprintf(sidecar,MAX_PATH+8,L"%s.ini",file); save_state(sidecar);
                wcscpy(status_text,L"Exported 30 s WAV + preset sidecar · Replay to listen");
            } else wcscpy(status_text,L"Export failed: check output path and imported assets");
            SetCursor(LoadCursor(NULL,IDC_ARROW));
        }
    } else if(id==ID_REPLAY) {
        if(last_export[0])wcscpy(file,last_export);
        if(choose(file,L"WAV audio\0*.wav\0\0",0,L"wav")) {
            stop();
            if(PlaySoundW(file,NULL,SND_ASYNC|SND_FILENAME|SND_NODEFAULT)) {
                preview=1; SetWindowTextW(play,L"■  Stop"); wcscpy(status_text,L"WAV playback · source file level · Stop ends playback");
            } else wcscpy(status_text,L"Playback failed: use PCM WAV");
        }
    } else if(id==ID_SAVE) {
        wcscpy(file,L"sound_baseline.ini");
        if(choose(file,L"Preset\0*.ini\0\0",1,L"ini")) { save_state(file); wcscpy(status_text,L"Preset saved · DSP " VSL_VERSION_W L" · seed 48271"); }
    } else if(id==ID_LOAD) {
        if(choose(file,L"Preset\0*.ini\0\0",0,L"ini")) {
            stop();
            if(!vsl_preset_load(file,&params,dna_file,ir_file)) { wcscpy(status_text,L"Preset has no VSL version");return; }
            params.ignition=0;params.start_id=0;params.throttle=params.brake=0;
            if(load_assets())wcscpy(status_text,L"Preset loaded · ready to listen");
            else { dna_file[0]=ir_file[0]=0; load_assets(); wcscpy(status_text,L"Asset unavailable · cleared imports; preset controls loaded"); }
            params=audio.engine->target; slider_values(); publish();
        }
    } else if(id==ID_DNA || id==ID_IR) {
        if(choose(file,id==ID_DNA?L"Oscillator DNA\0*.dna\0\0":L"Short mono/stereo IR (48 kHz, <=8192 samples)\0*.wav\0\0",0,id==ID_DNA?L"dna":L"wav")) {
            stop();
            if(id==ID_DNA)wcscpy(dna_file,file); else wcscpy(ir_file,file);
            if(load_assets())wcscpy(status_text,id==ID_DNA?L"Custom DNA loaded · root pitch occurs at 3000 RPM":L"Short IR loaded · Space controls wet mix");
            else { if(id==ID_DNA)dna_file[0]=0; else ir_file[0]=0; load_assets(); wcscpy(status_text,L"Import failed · DNA v1 or IR 48 kHz / max 8192 frames required"); }
            publish();
        }
    } else if(id==ID_CLEAR) {
        stop(); dna_file[0]=ir_file[0]=0; load_assets(); wcscpy(status_text,L"Imports cleared · procedural factory model"); publish();
    }
    InvalidateRect(window,NULL,FALSE);
}
static LRESULT CALLBACK procedure(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp) {
    if(msg==WM_CREATE) {
        int i; window=hwnd;
        profile=control(L"COMBOBOX",L"",CBS_DROPDOWNLIST|CBS_OWNERDRAWFIXED|CBS_HASSTRINGS|WS_VSCROLL,28,110,300,200,ID_PROFILE);
        SendMessageW(profile,CB_ADDSTRING,0,(LPARAM)L"V10 · 5.2 common pin");
        SendMessageW(profile,CB_ADDSTRING,0,(LPARAM)L"V8 · crossplane");
        SendMessageW(profile,CB_ADDSTRING,0,(LPARAM)L"Flat-six · turbo character");
        SendMessageW(profile,CB_ADDSTRING,0,(LPARAM)L"SCI-FI · oscillator DNA");
        SendMessageW(profile,CB_ADDSTRING,0,(LPARAM)L"V12 · naturally aspirated");
        drive=control(L"COMBOBOX",L"",CBS_DROPDOWNLIST|CBS_OWNERDRAWFIXED|CBS_HASSTRINGS,350,110,205,180,ID_DRIVE);
        SendMessageW(drive,CB_ADDSTRING,0,(LPARAM)L"RPM / load bench");
        SendMessageW(drive,CB_ADDSTRING,0,(LPARAM)L"Pedal driving");
        SendMessageW(drive,CB_ADDSTRING,0,(LPARAM)L"Auto drive · 30 s");
        pure=control(L"BUTTON",L"Pure OSC",BS_AUTOCHECKBOX,580,111,140,28,ID_PURE);
        cabin=control(L"BUTTON",L"Cabin preview",BS_AUTOCHECKBOX,730,111,180,28,ID_CABIN);
        vsl_drive_panel_create(window,font,156);
        for(i=0;i<8;++i) {
            sliders[i]=control(TRACKBAR_CLASSW,L"",TBS_HORZ|TBS_NOTICKS|WS_TABSTOP,xs[i],ys[i]+28,widths[i],32,200+i);
            SetWindowTextW(sliders[i],names[i]);
            SendMessageW(sliders[i],TBM_SETRANGE,TRUE,MAKELPARAM(0,1000));
        }
        play=control(L"BUTTON",L"▶  Monitor",BS_PUSHBUTTON|WS_TABSTOP,28,597,180,42,ID_PLAY);
        control(L"BUTTON",L"Export 30 s",BS_PUSHBUTTON|WS_TABSTOP,225,597,150,42,ID_EXPORT);
        control(L"BUTTON",L"Replay WAV",BS_PUSHBUTTON|WS_TABSTOP,392,597,150,42,ID_REPLAY);
        control(L"BUTTON",L"Save preset",BS_PUSHBUTTON|WS_TABSTOP,565,597,150,42,ID_SAVE);
        control(L"BUTTON",L"Load preset",BS_PUSHBUTTON|WS_TABSTOP,732,597,170,42,ID_LOAD);
        control(L"BUTTON",L"Import DNA",BS_PUSHBUTTON,28,659,125,30,ID_DNA);
        control(L"BUTTON",L"Import IR",BS_PUSHBUTTON,166,659,120,30,ID_IR);
        control(L"BUTTON",L"Clear imports",BS_PUSHBUTTON,299,659,135,30,ID_CLEAR);
        control(L"BUTTON",L"Sound detail",BS_PUSHBUTTON,450,659,135,30,ID_TUNING);
        control(L"BUTTON",L"New take",BS_PUSHBUTTON,600,659,94,30,ID_TAKE_NEW);
        control(L"BUTTON",L"Save take",BS_PUSHBUTTON,704,659,94,30,ID_TAKE_SAVE);
        control(L"BUTTON",L"Play take",BS_PUSHBUTTON,808,659,94,30,ID_TAKE_PLAY);
        slider_values(); SetTimer(hwnd,1,50,NULL); return 0;
    }
    if(msg==WM_COMMAND) { int id=LOWORD(wp);if((id!=ID_PROFILE&&id!=ID_DRIVE)||HIWORD(wp)==CBN_SELCHANGE)command(id);return 0; }
    if(msg==VSL_TUNING_CHANGED) { publish();return 0; }
    if(msg==WM_ACTIVATE && !replaying && LOWORD(wp)==WA_INACTIVE && (key_throttle||key_brake)) {
        if(key_throttle)params.throttle=0;if(key_brake)params.brake=0;
        key_throttle=key_brake=0;slider_values();publish();return 0;
    }
    if(msg==WM_MEASUREITEM) { ((MEASUREITEMSTRUCT*)lp)->itemHeight=26; return TRUE; }
    if(msg==WM_DRAWITEM) {
        DRAWITEMSTRUCT*d=(DRAWITEMSTRUCT*)lp; RECT r=d->rcItem; wchar_t label[256];
        HBRUSH fill; COLORREF ink;
        if(d->CtlType==ODT_COMBOBOX) {
            int item=d->itemID==(UINT)-1?(int)SendMessageW(d->hwndItem,CB_GETCURSEL,0,0):(int)d->itemID;
            fill=CreateSolidBrush(d->itemState&ODS_SELECTED?RGB(35,65,74):RGB(27,34,44));
            ink=RGB(226,236,245); label[0]=0;
            SendMessageW(d->hwndItem,CB_GETLBTEXT,item,(LPARAM)label);
            FillRect(d->hDC,&r,fill); DeleteObject(fill); r.left+=10;
            SelectObject(d->hDC,font); SetTextColor(d->hDC,ink); SetBkMode(d->hDC,TRANSPARENT);
            DrawTextW(d->hDC,label,-1,&r,DT_SINGLELINE|DT_VCENTER); return TRUE;
        }
        fill=CreateSolidBrush(d->CtlID==ID_PLAY?RGB(79,183,167):(d->itemState&ODS_SELECTED?RGB(49,66,82):RGB(33,43,56)));
        FillRect(d->hDC,&r,fill); DeleteObject(fill); GetWindowTextW(d->hwndItem,label,256);
        ink=d->CtlID==ID_PLAY?RGB(10,31,34):RGB(219,230,242);
        SelectObject(d->hDC,font); SetTextColor(d->hDC,ink); SetBkMode(d->hDC,TRANSPARENT);
        DrawTextW(d->hDC,label,-1,&r,DT_SINGLELINE|DT_CENTER|DT_VCENTER);
        if(d->itemState&ODS_FOCUS) { InflateRect(&r,-3,-3); DrawFocusRect(d->hDC,&r); }
        return TRUE;
    }
    if(msg==WM_HSCROLL) {
        if(replaying)return 0;
        int i;for(i=0;i<8;++i)if((HWND)lp==sliders[i]) {
            double v=SendMessageW(sliders[i],TBM_GETPOS,0,0)/1000.;
            if(i==0) { if(params.drive_mode==VSL_BENCH)params.rpm=v*10000;else params.throttle=v; }
            else if(i==1) { if(params.drive_mode==VSL_BENCH)params.load=v*2-1;else params.brake=v; }
            else {
                double *values[]={&params.dna,&params.pad,&params.noise,&params.width,&params.space,&params.master};
                *values[i-2]=v;
            }
        }
        publish();return 0;
    }
    if(msg==WM_CTLCOLORSTATIC || msg==WM_CTLCOLORBTN) {
        SetTextColor((HDC)wp,RGB(214,223,235)); SetBkColor((HDC)wp,RGB(20,25,34)); return (LRESULT)bg;
    }
    if(msg==WM_TIMER) {
        VslVoicing voice;
        if(ui_input_mode) {
            if(vsl_ui_input_tick(&ui_input_check,hwnd,profile,drive,play,&params,
                key_throttle,key_brake,workspace,input_capture))PostMessageW(hwnd,WM_CLOSE,0,0);
            return 0;
        }
        EnterCriticalSection(&audio.lock);voice=audio.voice;LeaveCriticalSection(&audio.lock);
        vsl_tuning_meters(&voice,params.pure_osc,audio.running);
        if(capture_preview && ++smoke_tick==15) {
            diagnostic_capture(diagnostic_path(L"ui_live_preview.bmp")); capture_preview=0;
        }
        if(smoke_mode) {
            ++smoke_tick;
            if(smoke_tick==5) {
                diagnostic_capture(diagnostic_path(L"ui_ready.bmp"));
                params.drive_mode=VSL_AUTODRIVE;params.propagation=1;
                params.pressure_texture=.653456789123456;params.structure_transfer=.617234567891234;
                params.response_shape=.613456789123456;params.event_color=.543456789123456;
                params.firing_source=VSL_SOURCE_VARIABLE;params.pulse_amount=.713456789123456;
                slider_values();publish();command(ID_TAKE_NEW);command(ID_START);
            }
            if(smoke_tick==40) {
                params.drive_mode=VSL_PEDALS;params.throttle=1;params.response_shape=.843456789123456;params.event_color=.783456789123456;params.firing_source=VSL_SOURCE_FIXED;params.pulse_amount=.893456789123456;slider_values();publish();
            }
            if(smoke_tick==90) {
                EnterCriticalSection(&audio.lock);smoke_shifts_before=audio.state.shift_events;LeaveCriticalSection(&audio.lock);
                command(ID_GEAR_UP);smoke_requested_gear=params.gear;
            }
            if(smoke_tick==110) {
                /* Observe the known nondefault device state before UI tests
                   intentionally change its switches and slider targets. */
                EnterCriticalSection(&audio.lock);
                smoke_propagation_active=audio.propagation_mix>.999&&audio.propagation_clamped_paths==0;
                smoke_character_active=audio.character_pressure_mix>.4&&audio.character_structure_mix>.4&&audio.character_events>100;
                smoke_response_active=audio.response_shape_mix>.4&&audio.response_pressure_events>100;
                smoke_color_active=audio.event_color_mix>.4&&audio.event_color_events>100&&audio.event_color_max_mod>.05;
                smoke_pulse_active=audio.pulse_mix>.8&&audio.pulse_events>100&&audio.pulse_overflow==0;
                LeaveCriticalSection(&audio.lock);
                HWND details=vsl_tuning_show(window,font,&params);
                vsl_tuning_meters(&voice,params.pure_osc,audio.running);
                diagnostic_capture_window(details,diagnostic_path(L"ui_detail.bmp"));
                {
                    VslParams loaded,saved=params,probe;wchar_t dna[MAX_PATH],ir[MAX_PATH];
                    SendMessageW(GetDlgItem(details,101),BM_CLICK,0,0);
                    SendMessageW(GetDlgItem(details,102),TBM_SETPOS,TRUE,420);
                    SendMessageW(details,WM_HSCROLL,0,(LPARAM)GetDlgItem(details,102));
                    smoke_fuel_controls=params.fuel_cut!=saved.fuel_cut&&fabs(params.pumping-.42)<1e-9;
                    probe=params;probe.fuel_cut=saved.fuel_cut;probe.pumping=saved.pumping;
                    smoke_control_isolation=memcmp(&probe,&saved,sizeof saved)==0;
                    SendMessageW(GetDlgItem(details,103),BM_CLICK,0,0);
                    smoke_mechanical_control=params.mechanical_model!=saved.mechanical_model;
                    probe=params;probe.fuel_cut=saved.fuel_cut;probe.pumping=saved.pumping;probe.mechanical_model=saved.mechanical_model;
                    smoke_control_isolation=smoke_control_isolation&&memcmp(&probe,&saved,sizeof saved)==0;
                    SendMessageW(GetDlgItem(details,104),BM_CLICK,0,0);
                    smoke_combustion_control=params.combustion_variation!=saved.combustion_variation;
                    probe=params;probe.fuel_cut=saved.fuel_cut;probe.pumping=saved.pumping;probe.mechanical_model=saved.mechanical_model;probe.combustion_variation=saved.combustion_variation;
                    smoke_control_isolation=smoke_control_isolation&&memcmp(&probe,&saved,sizeof saved)==0;
                    vsl_preset_save(diagnostic_path(L"ui_control_roundtrip.ini"),&params,dna_file,ir_file);
                    smoke_fuel_preset=vsl_preset_load(diagnostic_path(L"ui_control_roundtrip.ini"),&loaded,dna,ir)&&loaded.fuel_cut==params.fuel_cut&&fabs(loaded.pumping-.42)<1e-9;
                    smoke_mechanical_preset=loaded.mechanical_model==params.mechanical_model;
                    smoke_combustion_preset=loaded.combustion_variation==params.combustion_variation;
                    {
                        VslParams before=params,isolated;
                        SendMessageW(GetDlgItem(details,105),BM_CLICK,0,0);
                        isolated=params;isolated.propagation=before.propagation;
                        smoke_propagation_control=params.propagation!=before.propagation&&memcmp(&isolated,&before,sizeof before)==0;
                        SendMessageW(GetDlgItem(details,105),BM_CLICK,0,0);
                        smoke_propagation_control=smoke_propagation_control&&params.propagation==1&&memcmp(&params,&before,sizeof before)==0;
                        vsl_preset_save(diagnostic_path(L"ui_control_roundtrip.ini"),&params,dna_file,ir_file);
                        smoke_propagation_preset=vsl_preset_load(diagnostic_path(L"ui_control_roundtrip.ini"),&loaded,dna,ir)&&loaded.propagation==1;
                        vsl_preset_save(diagnostic_path(L"ui_v013_preset.ini"),&saved,dna_file,ir_file);
                        WritePrivateProfileStringW(L"VSL",L"version",L"0.13.0",diagnostic_path(L"ui_v013_preset.ini"));
                        WritePrivateProfileStringW(L"VSL",L"propagation",NULL,diagnostic_path(L"ui_v013_preset.ini"));
                        smoke_propagation_legacy=vsl_preset_load(diagnostic_path(L"ui_v013_preset.ini"),&loaded,dna,ir)&&loaded.propagation==0&&loaded.mechanical_model==saved.mechanical_model&&loaded.combustion_variation==saved.combustion_variation;
                    }
                    vsl_preset_save(diagnostic_path(L"ui_v08_preset.ini"),&saved,dna_file,ir_file);
                    WritePrivateProfileStringW(L"VSL",L"version",L"0.8.0",diagnostic_path(L"ui_v08_preset.ini"));
                    WritePrivateProfileStringW(L"VSL",L"combustion_variation",NULL,diagnostic_path(L"ui_v08_preset.ini"));
                    smoke_combustion_legacy_preset=vsl_preset_load(diagnostic_path(L"ui_v08_preset.ini"),&loaded,dna,ir)&&loaded.combustion_variation==0&&loaded.mechanical_model==saved.mechanical_model;
                    vsl_preset_save(diagnostic_path(L"ui_legacy_preset.ini"),&saved,dna_file,ir_file);
                    WritePrivateProfileStringW(L"VSL",L"version",L"0.7.0",diagnostic_path(L"ui_legacy_preset.ini"));
                    WritePrivateProfileStringW(L"VSL",L"mechanical_model",NULL,diagnostic_path(L"ui_legacy_preset.ini"));
                    WritePrivateProfileStringW(L"VSL",L"combustion_variation",NULL,diagnostic_path(L"ui_legacy_preset.ini"));
                    smoke_mechanical_legacy_preset=vsl_preset_load(diagnostic_path(L"ui_legacy_preset.ini"),&loaded,dna,ir)&&loaded.mechanical_model==0&&fabs(loaded.release_time-saved.release_time)<1e-9;
                    {
                        VslParams before=params,isolated;
                        SendMessageW(GetDlgItem(details,106),TBM_SETPOS,TRUE,731);
                        SendMessageW(details,WM_HSCROLL,0,(LPARAM)GetDlgItem(details,106));
                        isolated=params;isolated.pressure_texture=before.pressure_texture;
                        smoke_character_control=params.pressure_texture==.731&&!memcmp(&isolated,&before,sizeof before);
                        before=params;
                        SendMessageW(GetDlgItem(details,107),TBM_SETPOS,TRUE,437);
                        SendMessageW(details,WM_HSCROLL,0,(LPARAM)GetDlgItem(details,107));
                        isolated=params;isolated.structure_transfer=before.structure_transfer;
                        smoke_character_control=smoke_character_control&&params.structure_transfer==.437&&!memcmp(&isolated,&before,sizeof before);
                        vsl_preset_save(diagnostic_path(L"ui_character_roundtrip.ini"),&params,dna_file,ir_file);
                        smoke_character_preset=vsl_preset_load(diagnostic_path(L"ui_character_roundtrip.ini"),&loaded,dna,ir)&&
                            loaded.pressure_texture==params.pressure_texture&&loaded.structure_transfer==params.structure_transfer;
                        /* Verify exact off-grid values, including untouched old parameters. */
                        vsl_preset_save(diagnostic_path(L"ui_character_precise.ini"),&saved,dna_file,ir_file);
                        smoke_character_preset=smoke_character_preset&&vsl_preset_load(diagnostic_path(L"ui_character_precise.ini"),&loaded,dna,ir)&&!memcmp(&loaded,&saved,sizeof saved);
                        WritePrivateProfileStringW(L"VSL",L"version",L"0.15.0",diagnostic_path(L"ui_character_precise.ini"));
                        WritePrivateProfileStringW(L"VSL",L"pressure_texture",NULL,diagnostic_path(L"ui_character_precise.ini"));
                        WritePrivateProfileStringW(L"VSL",L"structure_transfer",NULL,diagnostic_path(L"ui_character_precise.ini"));
                        WritePrivateProfileStringW(L"VSL",L"response_shape",NULL,diagnostic_path(L"ui_character_precise.ini"));
                        WritePrivateProfileStringW(L"VSL",L"event_color",NULL,diagnostic_path(L"ui_character_precise.ini"));
                        before=saved;before.pressure_texture=before.structure_transfer=before.response_shape=before.event_color=0;
                        smoke_character_legacy=vsl_preset_load(diagnostic_path(L"ui_character_precise.ini"),&loaded,dna,ir)&&!memcmp(&loaded,&before,sizeof before);
                    }
                    {
                        VslParams before=params,isolated;
                        SendMessageW(GetDlgItem(details,108),TBM_SETPOS,TRUE,317);
                        SendMessageW(details,WM_HSCROLL,0,(LPARAM)GetDlgItem(details,108));
                        isolated=params;isolated.response_shape=before.response_shape;
                        smoke_response_control=params.response_shape==.317&&!memcmp(&isolated,&before,sizeof before);
                        vsl_preset_save(diagnostic_path(L"ui_response_roundtrip.ini"),&params,dna_file,ir_file);
                        smoke_response_preset=vsl_preset_load(diagnostic_path(L"ui_response_roundtrip.ini"),&loaded,dna,ir)&&!memcmp(&loaded,&params,sizeof params);
                        vsl_preset_save(diagnostic_path(L"ui_response_legacy.ini"),&saved,dna_file,ir_file);
                        WritePrivateProfileStringW(L"VSL",L"version",L"0.17.0",diagnostic_path(L"ui_response_legacy.ini"));
                        WritePrivateProfileStringW(L"VSL",L"response_shape",NULL,diagnostic_path(L"ui_response_legacy.ini"));
                        WritePrivateProfileStringW(L"VSL",L"event_color",NULL,diagnostic_path(L"ui_response_legacy.ini"));
                        before=saved;before.response_shape=before.event_color=0;
                        smoke_response_legacy=vsl_preset_load(diagnostic_path(L"ui_response_legacy.ini"),&loaded,dna,ir)&&!memcmp(&loaded,&before,sizeof before);
                    }
                    {
                        VslParams before=params,isolated;
                        SendMessageW(GetDlgItem(details,109),TBM_SETPOS,TRUE,571);
                        SendMessageW(details,WM_HSCROLL,0,(LPARAM)GetDlgItem(details,109));
                        isolated=params;isolated.event_color=before.event_color;
                        smoke_color_control=params.event_color==.571&&!memcmp(&isolated,&before,sizeof before);
                        vsl_preset_save(diagnostic_path(L"ui_color_roundtrip.ini"),&params,dna_file,ir_file);
                        smoke_color_preset=vsl_preset_load(diagnostic_path(L"ui_color_roundtrip.ini"),&loaded,dna,ir)&&!memcmp(&loaded,&params,sizeof params);
                        vsl_preset_save(diagnostic_path(L"ui_color_legacy.ini"),&saved,dna_file,ir_file);
                        WritePrivateProfileStringW(L"VSL",L"version",L"0.18.0",diagnostic_path(L"ui_color_legacy.ini"));
                        WritePrivateProfileStringW(L"VSL",L"event_color",NULL,diagnostic_path(L"ui_color_legacy.ini"));
                        before=saved;before.event_color=0;
                        smoke_color_legacy=vsl_preset_load(diagnostic_path(L"ui_color_legacy.ini"),&loaded,dna,ir)&&!memcmp(&loaded,&before,sizeof before);
                    }
                    {
                        VslParams before=params,isolated;int mode_ok,amount_ok;
                        SendMessageW(GetDlgItem(details,110),CB_SETCURSEL,VSL_SOURCE_VARIABLE,0);
                        SendMessageW(details,WM_COMMAND,MAKEWPARAM(110,CBN_SELCHANGE),(LPARAM)GetDlgItem(details,110));
                        isolated=params;isolated.firing_source=before.firing_source;
                        mode_ok=params.firing_source==VSL_SOURCE_VARIABLE&&!memcmp(&isolated,&before,sizeof before);
                        before=params;
                        SendMessageW(GetDlgItem(details,111),TBM_SETPOS,TRUE,637);
                        SendMessageW(details,WM_HSCROLL,0,(LPARAM)GetDlgItem(details,111));
                        isolated=params;isolated.pulse_amount=before.pulse_amount;
                        amount_ok=params.pulse_amount==.637&&!memcmp(&isolated,&before,sizeof before);
                        smoke_pulse_control=mode_ok&&amount_ok;
                        vsl_preset_save(diagnostic_path(L"ui_pulse_roundtrip.ini"),&params,dna_file,ir_file);
                        smoke_pulse_preset=vsl_preset_load(diagnostic_path(L"ui_pulse_roundtrip.ini"),&loaded,dna,ir)&&!memcmp(&loaded,&params,sizeof params);
                        vsl_preset_save(diagnostic_path(L"ui_pulse_legacy.ini"),&saved,dna_file,ir_file);
                        WritePrivateProfileStringW(L"VSL",L"version",L"0.19.0",diagnostic_path(L"ui_pulse_legacy.ini"));
                        WritePrivateProfileStringW(L"VSL",L"firing_source",NULL,diagnostic_path(L"ui_pulse_legacy.ini"));
                        WritePrivateProfileStringW(L"VSL",L"pulse_amount",NULL,diagnostic_path(L"ui_pulse_legacy.ini"));
                        before=saved;before.firing_source=VSL_SOURCE_OSC;before.pulse_amount=1;
                        smoke_pulse_legacy=vsl_preset_load(diagnostic_path(L"ui_pulse_legacy.ini"),&loaded,dna,ir)&&!memcmp(&loaded,&before,sizeof before);
                    }
                    params=saved;
                    SendMessageW(sliders[7],TBM_SETPOS,TRUE,371);
                    SendMessageW(window,WM_HSCROLL,0,(LPARAM)sliders[7]);
                    probe=params;probe.master=saved.master;
                    smoke_control_isolation=smoke_control_isolation&&fabs(params.master-.371)<1e-9&&memcmp(&probe,&saved,sizeof saved)==0;
                    params=saved;slider_values();vsl_tuning_sync();publish();
                }
                EnterCriticalSection(&audio.lock); smoke_audio_ok=audio.running&&audio.peak>.001; LeaveCriticalSection(&audio.lock);
                EnterCriticalSection(&audio.lock);smoke_running_ok=audio.state.lifecycle==VSL_RUNNING;smoke_shift_ok=audio.state.shift_events>smoke_shifts_before && audio.state.gear==smoke_requested_gear && !params.auto_gear;LeaveCriticalSection(&audio.lock);
                EnterCriticalSection(&audio.lock);
                smoke_vehicle_ok=audio.state.vehicle.effective_mass_kg>=1670 &&
                    audio.state.vehicle.wheel_force_n>0 && audio.state.speed_kph>0 &&
                    audio.state.vehicle.transmitted_gear==audio.state.gear;
                smoke_coupling_ok=audio.state.vehicle.solver_active&&audio.state.coupling_audit.steps>500&&
                    audio.state.coupling_audit.max_energy_error_j<1e-6;
                LeaveCriticalSection(&audio.lock);
                diagnostic_capture(diagnostic_path(L"ui_listening.bmp"));
                params.throttle=0;slider_values();publish();
            }
            if(smoke_tick==140) { params.ignition=0;slider_values();publish(); }
            if(smoke_tick==175) {
                FILE*f; char path[MAX_PATH*4],dna[MAX_PATH*4],ir[MAX_PATH*4]; int rendered;
                EnterCriticalSection(&audio.lock);smoke_shutdown_ok=audio.state.lifecycle==VSL_OFF;LeaveCriticalSection(&audio.lock);
                stop(); save_state(diagnostic_path(L"ui_smoke.ini"));
                utf8(dna_file,dna,sizeof dna); utf8(ir_file,ir,sizeof ir);
                utf8(diagnostic_path(L"ui_smoke.wav"),path,sizeof path);
                { VslParams test=params;test.ignition=1;test.start_id=1;rendered=vsl_render_file(path,&test,1,0,dna,ir); }
                f=_wfopen(diagnostic_path(L"ui_smoke.json"),L"w");
                if(f) {
                    fprintf(f,"{\"waveOut_opened_and_queued_audio\":%s,\"export_succeeded\":%s,\"running_latch\":%s,\"manual_shift\":%s,\"shutdown_to_off\":%s,",smoke_audio_ok?"true":"false",rendered?"true":"false",smoke_running_ok?"true":"false",smoke_shift_ok?"true":"false",smoke_shutdown_ok?"true":"false");
                    fprintf(f,"\"fuel_controls\":%s,\"fuel_preset_roundtrip\":%s,\"control_isolation\":%s,",smoke_fuel_controls?"true":"false",smoke_fuel_preset?"true":"false",smoke_control_isolation?"true":"false");
                    fprintf(f,"\"mechanical_control\":%s,\"mechanical_preset_roundtrip\":%s,",smoke_mechanical_control?"true":"false",smoke_mechanical_preset?"true":"false");
                    fprintf(f,"\"legacy_preset_retains_mechanical_voice\":%s,",smoke_mechanical_legacy_preset?"true":"false");
                    fprintf(f,"\"longitudinal_model_active\":%s,",smoke_vehicle_ok?"true":"false");
                    fprintf(f,"\"two_inertia_coupling_active\":%s,",smoke_coupling_ok?"true":"false");
                    fprintf(f,"\"propagation_control\":%s,\"propagation_preset_roundtrip\":%s,\"legacy_preset_retains_spatial_renderer\":%s,",smoke_propagation_control?"true":"false",smoke_propagation_preset?"true":"false",smoke_propagation_legacy?"true":"false");
                    fprintf(f,"\"propagation_active_on_device\":%s,",smoke_propagation_active?"true":"false");
                    fprintf(f,"\"character_controls\":%s,\"character_preset_roundtrip\":%s,\"character_legacy_preset\":%s,\"character_active_on_device\":%s,",smoke_character_control?"true":"false",smoke_character_preset?"true":"false",smoke_character_legacy?"true":"false",smoke_character_active?"true":"false");
                    fprintf(f,"\"response_control\":%s,\"response_preset_roundtrip\":%s,\"response_legacy_preset\":%s,\"response_active_on_device\":%s,",smoke_response_control?"true":"false",smoke_response_preset?"true":"false",smoke_response_legacy?"true":"false",smoke_response_active?"true":"false");
                    fprintf(f,"\"pulse_controls\":%s,\"pulse_preset_roundtrip\":%s,\"pulse_legacy_preset\":%s,\"pulse_active_on_device\":%s,",smoke_pulse_control?"true":"false",smoke_pulse_preset?"true":"false",smoke_pulse_legacy?"true":"false",smoke_pulse_active?"true":"false");
                    fprintf(f,"\"event_color_control\":%s,\"event_color_preset_roundtrip\":%s,\"event_color_legacy_preset\":%s,\"event_color_active_on_device\":%s,",smoke_color_control?"true":"false",smoke_color_preset?"true":"false",smoke_color_legacy?"true":"false",smoke_color_active?"true":"false");
                    fprintf(f,"\"combustion_control\":%s,\"combustion_preset_roundtrip\":%s,\"legacy_preset_retains_pressure_voice\":%s,",smoke_combustion_control?"true":"false",smoke_combustion_preset?"true":"false",smoke_combustion_legacy_preset?"true":"false");
                    fprintf(f,"\"device_stream_muted\":%s,\"render_ms_max\":%.4f,\"render_ms_mean\":%.4f,\"block_frames\":%d,\"blocks\":%u,\"wall_seconds\":%.4f,\"device_seconds\":%.4f,\"queue_empty_observations\":%u,\"dsp\":\"%s\",\"profile_count\":%d}",audio.diagnostic_mute?"true":"false",audio.render_ms_max,audio.render_ms_total/fmax(1,audio.rendered_blocks),VSL_DEVICE_BLOCK,audio.rendered_blocks,audio.worker_wall_seconds,audio.device_seconds,audio.queue_empty_observations,VSL_VERSION,(int)SendMessageW(profile,CB_GETCOUNT,0,0));fclose(f);
                }
                {
                    VslParams unchanged=params;int locked;
                    before_replay=params;replaying=1;take_controls(0);
                    command(ID_GEAR_UP);SendMessageW(window,WM_HSCROLL,0,(LPARAM)sliders[7]);
                    {
                        HWND detail=vsl_tuning_show(window,font,&params);int c;
                        for(c=106;c<=109;++c) {
                            SendMessageW(GetDlgItem(detail,c),TBM_SETPOS,TRUE,123);
                            SendMessageW(detail,WM_HSCROLL,0,(LPARAM)GetDlgItem(detail,c));
                        }
                        SendMessageW(GetDlgItem(detail,111),TBM_SETPOS,TRUE,123);
                        SendMessageW(detail,WM_HSCROLL,0,(LPARAM)GetDlgItem(detail,111));
                        SendMessageW(GetDlgItem(detail,110),CB_SETCURSEL,VSL_SOURCE_VARIABLE,0);
                        SendMessageW(detail,WM_COMMAND,MAKEWPARAM(110,CBN_SELCHANGE),(LPARAM)GetDlgItem(detail,110));
                        locked=!IsWindowEnabled(detail)&&!IsWindowEnabled(sliders[0])&&!IsWindowEnabled(profile)&&!IsWindowEnabled(GetDlgItem(window,ID_START))&&IsWindowEnabled(play)&&!memcmp(&params,&unchanged,sizeof params);
                    }
                    diagnostic_capture(diagnostic_path(L"ui_take_replay.bmp"));
                    vsl_take_smoke(&audio,&takes,workspace,locked);
                    stop();
                    {
                        VslParams restored=params;FILE *check;
                        restored.ignition=unchanged.ignition;restored.start_id=unchanged.start_id;
                        restored.throttle=unchanged.throttle;restored.brake=unchanged.brake;
                        check=_wfopen(diagnostic_path(L"ui_take_controls.json"),L"w");
                        if(check) {
                            fprintf(check,"{\"live_params_restored\":%d,\"ignition_and_pedals_reset\":%d,\"engine_frame_zero\":%d,\"controls_enabled\":%d}\n",!memcmp(&restored,&unchanged,sizeof restored),!params.ignition&&!params.start_id&&!params.throttle&&!params.brake,audio.engine->frame==0,IsWindowEnabled(sliders[0])&&IsWindowEnabled(profile)&&IsWindowEnabled(GetDlgItem(window,ID_START)));
                            fclose(check);
                        }
                    }
                }
                PostMessageW(window,WM_CLOSE,0,0);
            }
        }
        if(!audio.running&&audio.thread&&audio.take_mode) {
            int was_replay=audio.take_mode==2,match=audio.take_hash_match,limit=audio.take_limit;
            stop();
            if(was_replay)wcscpy(status_text,match?L"Take replay complete · exact stereo DSP hash verified":L"Replay incomplete · reconstruction hash not verified");
            else if(limit&&takes.saved)wcscpy(status_text,L"Recording limit reached · valid take saved to performances");
        }
        if(replaying) {
            EnterCriticalSection(&audio.lock);params=audio.actual_target;LeaveCriticalSection(&audio.lock);
            slider_values();
        }
        if(audio.error[0] && !audio.running) { swprintf(status_text,256,L"Audio error: %.200s",audio.error); SetWindowTextW(play,L"▶  Listen"); }
        if(params.drive_mode==VSL_AUTODRIVE && audio.running) {
            double pedal,brake;EnterCriticalSection(&audio.lock);pedal=audio.state.throttle;brake=audio.state.brake;LeaveCriticalSection(&audio.lock);
            SendMessageW(sliders[0],TBM_SETPOS,TRUE,(LPARAM)(pedal*1000));SendMessageW(sliders[1],TBM_SETPOS,TRUE,(LPARAM)(brake*1000));
        }
        InvalidateRect(hwnd,NULL,FALSE); return 0;
    }
    if(msg==WM_PAINT || msg==WM_PRINTCLIENT) {
        PAINTSTRUCT ps; RECT rect; HDC dc=msg==WM_PAINT?BeginPaint(hwnd,&ps):(HDC)wp,mem=CreateCompatibleDC(dc);
        HBITMAP bitmap; HGDIOBJ old; wchar_t s[128],gear_text[12];double rpm=0,load=0,peak=0;VslDrive state={0};
        float scope[256]={0}; int i; HPEN pen;
        GetClientRect(hwnd,&rect); bitmap=CreateCompatibleBitmap(dc,rect.right,rect.bottom); old=SelectObject(mem,bitmap);
        FillRect(mem,&rect,bg);
        EnterCriticalSection(&audio.lock);
        state=audio.state;rpm=state.rpm;load=state.load;
        if(audio.running) { rpm=audio.rpm;load=audio.load;peak=audio.peak;memcpy(scope,audio.scope,sizeof scope); }
        LeaveCriticalSection(&audio.lock);
        text_at(mem,28,24,L"VEHICLE SOUND LAB",title_font,RGB(239,244,250));
        text_at(mem,30,65,L"DNA   /   BODY   /   TEXTURE",small_font,RGB(123,148,177));
        text_at(mem,715,35,L"RESEARCH BUILD  " VSL_APP_VERSION_W,small_font,RGB(102,184,174));
        swprintf(s,128,L"%S  /  %S%s",vsl_lifecycle_name(state.lifecycle),vsl_operating_name(state.operating),state.fuel.mode==VSL_FUEL_CUT?L"  /  FUEL CUT":(state.fuel.mode==VSL_FUEL_RESUME?L"  /  REFUEL":L""));
        text_at(mem,28,209,s,small_font,RGB(122,146,170));
        swprintf(s,128,L"%04.0f",rpm); text_at(mem,26,232,s,large,RGB(113,222,203));
        if(state.gear)swprintf(gear_text,12,L"G%d",state.gear);else wcscpy(gear_text,L"N");
        swprintf(s,128,L"RPM     %03.0f km/h     %s",state.speed_kph,gear_text);text_at(mem,194,258,s,font,RGB(144,165,186));
        swprintf(s,128,L"LOAD  %+.0f%%     ·     %.1f dBFS",load*100,20*log10(fmax(peak,.000001)));
        text_at(mem,480,209,s,small_font,RGB(148,165,186));
        pen=CreatePen(PS_SOLID,1,RGB(84,174,164)); SelectObject(mem,pen);
        for(i=0;i<256;++i) { int x=480+i*422/255,y=259-(int)(scope[i]*65); if(!i)MoveToEx(mem,x,y,NULL); else LineTo(mem,x,y); }
        SelectObject(mem,GetStockObject(BLACK_PEN)); DeleteObject(pen);
        for(i=0;i<8;++i) {
            int bench=params.drive_mode==VSL_BENCH;
            double values[8]={bench?params.rpm:params.throttle*100,bench?params.load*100:params.brake*100,params.dna*100,params.pad*100,params.noise*100,params.width*100,params.space*100,params.master*100};
            if(params.drive_mode==VSL_AUTODRIVE) { values[0]=state.throttle*100;values[1]=state.brake*100; }
            const wchar_t *label=bench&&i<2?(i==0?L"RPM":L"SIGNED LOAD"):names[i];
            text_at(mem,xs[i],ys[i],label,small_font,RGB(158,176,196));
            swprintf(s,128,bench&&i==0?L"%.0f":L"%.0f%%",values[i]);
            text_at(mem,xs[i]+widths[i]-62,ys[i],s,small_font,RGB(219,230,241));
        }
        text_at(mem,28,364,params.pure_osc?L"OSC only · BODY, NVH, events and room bypassed":L"W / S: throttle / brake     Q / E: gear down / up     Start begins ignition sequence",small_font,RGB(99,171,164));
        text_at(mem,28,559,L"Stereo object monitor · exterior / cabin preview · separate 7.1.4 offline renderer",small_font,RGB(126,143,163));
        text_at(mem,745,65,dna_file[0]?L"CUSTOM DNA ACTIVE":L"FACTORY DNA",small_font,RGB(102,169,161));
        if(audio.take_mode) {
            uint64_t frames;unsigned events;
            EnterCriticalSection(&audio.lock);frames=audio.take_frames;events=audio.take_events;LeaveCriticalSection(&audio.lock);
            swprintf(s,128,L"%s  %.1f s  /  %u input events",audio.take_mode==1?L"REC":L"REPLAY",frames/48000.,events);
            text_at(mem,28,690,s,small_font,RGB(113,222,203));
        }
        text_at(mem,28,716,status_text,small_font,RGB(151,170,191));
        BitBlt(dc,0,0,rect.right,rect.bottom,mem,0,0,SRCCOPY);
        SelectObject(mem,old); DeleteObject(bitmap); DeleteDC(mem); if(msg==WM_PAINT)EndPaint(hwnd,&ps); return 0;
    }
    if(msg==WM_ERASEBKGND)return 1;
    if(msg==WM_CLOSE) {
        stop();if(!vsl_takes_preserve(&takes,workspace))return 0;
        DestroyWindow(hwnd);return 0;
    }
    if(msg==WM_DESTROY) { KillTimer(hwnd,1); PostQuitMessage(0); return 0; }
    return DefWindowProcW(hwnd,msg,wp,lp);
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,LPWSTR args,int show) {
    WNDCLASSW cls={0}; MSG msg; INITCOMMONCONTROLSEX controls={sizeof controls,ICC_BAR_CLASSES};
    RECT size={0,0,940,760}; wchar_t *slash;
    (void)previous;
    smoke_mode=wcsstr(args,L"--smoke-test")!=NULL;
    capture_preview=wcsstr(args,L"--preview-capture")!=NULL;
    ui_input_mode=wcsstr(args,L"--ui-input-check")!=NULL;
    if(ui_input_mode&&(smoke_mode||capture_preview))return 2;
    SetProcessDPIAware(); InitCommonControlsEx(&controls);
    GetModuleFileNameW(NULL,workspace,MAX_PATH); slash=wcsrchr(workspace,L'\\'); if(slash)*slash=0;
    {
        wchar_t candidate[MAX_PATH],probe[MAX_PATH];int i;
        wcscpy(candidate,workspace);
        for(i=0;i<4;++i) {
            swprintf(probe,MAX_PATH,L"%s\\CMakeLists.txt",candidate);
            if(GetFileAttributesW(probe)!=INVALID_FILE_ATTRIBUTES) { wcscpy(workspace,candidate);break; }
            slash=wcsrchr(candidate,L'\\');if(!slash)break;*slash=0;
        }
    }
    if(smoke_mode||capture_preview||ui_input_mode) {
        wchar_t directory[MAX_PATH];swprintf(directory,MAX_PATH,L"%s\\renders\\%s",workspace,VSL_DIAGNOSTIC_FOLDER_W);CreateDirectoryW(directory,NULL);
    }
    font=CreateFontW(-17,0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
    small_font=CreateFontW(-14,0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
    title_font=CreateFontW(-27,0,0,0,FW_SEMIBOLD,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
    large=CreateFontW(-48,0,0,0,FW_LIGHT,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
    bg=CreateSolidBrush(RGB(20,25,34)); card=CreateSolidBrush(RGB(28,35,46));
    params=vsl_default_params(0);params.drive_mode=VSL_PEDALS;params.ignition=0;params.start_id=0;vsl_audio_init(&audio);
    audio.diagnostic_mute=smoke_mode||ui_input_mode;
    if(!audio.engine)return 2;
    cls.lpfnWndProc=procedure; cls.hInstance=instance; cls.lpszClassName=L"VehicleSoundLab";
    cls.hCursor=LoadCursor(NULL,IDC_ARROW); cls.hbrBackground=bg; RegisterClassW(&cls);
    AdjustWindowRect(&size,WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,FALSE);
    window=CreateWindowExW(0,cls.lpszClassName,L"Vehicle Sound Lab · V10 Research " VSL_APP_VERSION_W,WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,
        CW_USEDEFAULT,CW_USEDEFAULT,size.right-size.left,size.bottom-size.top,NULL,NULL,instance,NULL);
    ShowWindow(window,show); UpdateWindow(window);
    while(GetMessageW(&msg,NULL,0,0)>0) {
        VslDriverKey key=replaying?VSL_KEY_NONE:vsl_driver_key(window,&msg,params.drive_mode==VSL_PEDALS,key_throttle,key_brake);
        if(key!=VSL_KEY_NONE) {
            if(key==VSL_KEY_CONSUMED)continue;
            if(key==VSL_KEY_THROTTLE_DOWN||key==VSL_KEY_THROTTLE_UP)params.throttle=key_throttle=key==VSL_KEY_THROTTLE_DOWN;
            else if(key==VSL_KEY_BRAKE_DOWN||key==VSL_KEY_BRAKE_UP)params.brake=key_brake=key==VSL_KEY_BRAKE_DOWN;
            else command(key==VSL_KEY_GEAR_DOWN?ID_GEAR_DOWN:ID_GEAR_UP);
            slider_values();publish();continue;
        }
        if(!IsDialogMessageW(window,&msg)) { TranslateMessage(&msg);DispatchMessageW(&msg); }
    }
    vsl_audio_destroy(&audio);vsl_takes_free(&takes); DeleteObject(font); DeleteObject(small_font); DeleteObject(large); DeleteObject(title_font);
    DeleteObject(bg); DeleteObject(card); return 0;
}

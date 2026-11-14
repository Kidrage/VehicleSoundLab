#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <commctrl.h>
#include <shellapi.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include "audio.h"
#include "models.h"
#include "takes.h"
#include "../startup_detail_host_v1/ui_checks.h"
#include "../drive_resonance_v1/ui_checks.h"
#include "resonant_detail_io/profile.h"
#include "stereo_resonance_io/profile.h"
#include "../full_recipe_drive_v1/models.h"
#include "../idle_drive_v1/models.h"
#include "../fine_idle_drive_v1/models.h"
#include "../catalog_drive_v1/session.h"
#include "../catalog_drive_v1/ui_checks.h"
static AmModels models;static SaBank bank;static AmAudio audio;
static StProfile startup_profile;static int startup_study;
static CbProfile catch_profile;static int catch_study;
static int startup_detail_study;static wchar_t ui_check_path[4096];
static int resonant_study;static DrsBank resonant_bank;static RdtProfile resonant_profile;
static RvsProfile stereo_profile;
static FrModels full_recipe;
static IdModels idle_models;static int idle_study;
static FidModels fine_idle_models;static int fine_idle_study;
static CdSession catalog;static int catalog_mode;
static HWND slider[9],label[9],status,telemetry,voice,mode,gear,auxiliary,listen_choice;
static HFONT font,heading;static int muted,bank_index,auxiliary_index;
static const int minimum[]={0,0,700,-24,0,0,0,0,0},maximum[]={100,100,8500,0,100,100,100,100,100},initial[]={0,0,1200,-6,70,0,0,0,0};
static const AdConfig *catalog_config(void) {
    return audio.transport==2&&audio.ready?&audio.take.assets->config:&audio.config;
}
static void catalog_flags(void) {
    const AdConfig *c;if(!catalog_mode)return;c=catalog_config();
    resonant_study=c->recipe_bank?3:c->resonant_bank?1:0;
    startup_study=c->startup_profile!=NULL;catch_study=c->catch_profile!=NULL;
    idle_study=c->idle_profile||c->fine_idle_profile;fine_idle_study=c->fine_idle_profile!=NULL;
}
static double *aux_amount(AdControl *c,int index) {
    if(catalog_mode)return dc_aux_amount(c,index);
    switch(index) {
    case 0:return &c->mix.intake_gain;case 1:return &c->mix.mechanical_gain;
    case 2:return &c->mix.air_gain;case 3:return &c->mix.road_gain;case 4:return &c->mix.wind_gain;
    case 5:return idle_study?&c->mix.idle_mix:&c->mix.startup_gain;
    case 6:return fine_idle_study?&c->mix.idle_motion:&c->mix.catch_gain;
    default:return &c->mix.idle_detail;
    }
}

static HWND item(HWND owner,const wchar_t *kind,const wchar_t *text,DWORD style,int id,int x,int y,int w,int h) {
    HWND child=CreateWindowW(kind,text,WS_CHILD|WS_VISIBLE|style,x,y,w,h,owner,(HMENU)(INT_PTR)id,NULL,NULL);
    SendMessageW(child,WM_SETFONT,(WPARAM)font,TRUE);return child;
}
static void labels(HWND owner) {
    AdControl c=am_audio_get(&audio);wchar_t text[128];int i,playing=am_audio_replaying(&audio),locked=playing||(catalog_mode&&audio.transport==2);
    const AdConfig *cap=catalog_mode?catalog_config():&audio.config;catalog_flags();
    swprintf(text,128,L"油门    %.0f%%",c.drive.throttle*100);SetWindowTextW(label[0],text);
    swprintf(text,128,L"制动    %.0f%%",c.drive.brake*100);SetWindowTextW(label[1],text);
    swprintf(text,128,L"台架转速    %.0f RPM",c.drive.rpm);SetWindowTextW(label[2],text);
    swprintf(text,128,L"输出    %.0f dB",20*log10(fmax(1e-12,c.mix.gain/.5)));SetWindowTextW(label[3],text);
    swprintf(text,128,L"空间宽度    %.0f%%",c.mix.width*100);SetWindowTextW(label[4],text);
    swprintf(text,128,L"房间量    %.0f%%",c.mix.room*100);SetWindowTextW(label[5],text);
    swprintf(text,128,resonant_study?L"连续共振细节    %.0f%%":startup_detail_study?L"声纹细节    %.0f%%":L"高频细节    %.0f%%",
        (resonant_study?c.mix.resonant_gain:c.mix.residual_gain)*100);SetWindowTextW(label[6],text);
    swprintf(text,128,resonant_study==3?L"相干低频    %.0f%%":L"低频分层    %.0f%%",
        (resonant_study==3?c.mix.coherent_low_gain:c.mix.body_mix)*100);SetWindowTextW(label[7],text);
    SendMessageW(slider[7],TBM_SETPOS,TRUE,(int)((resonant_study==3?c.mix.coherent_low_gain:c.mix.body_mix)*100));
    swprintf(text,128,L"声层量    %.0f%%",*aux_amount(&c,auxiliary_index)*100);SetWindowTextW(label[8],text);
    SendMessageW(slider[8],TBM_SETPOS,TRUE,(int)(*aux_amount(&c,auxiliary_index)*100));
    EnableWindow(auxiliary,!locked);
    SendMessageW(listen_choice,CB_SETCURSEL,am_audio_listen_get(&audio),0);
    for(i=0;i<9;++i)EnableWindow(slider[i],!locked);
    EnableWindow(slider[6],!locked&&(resonant_study?cap->resonant_bank!=NULL:cap->residual_bank!=NULL));
    if(catalog_mode) {
        EnableWindow(slider[7],!locked&&dc_body_enabled(cap));
        if(!dc_body_enabled(cap))SetWindowTextW(label[7],L"低频层 · 未配置");
    }
    SendMessageW(slider[6],TBM_SETPOS,TRUE,(int)((resonant_study?c.mix.resonant_gain:c.mix.residual_gain)*100));
    if(auxiliary_index==5&&!audio.config.startup_profile&&!idle_study)EnableWindow(slider[8],FALSE);
    if(auxiliary_index==6&&!audio.config.catch_profile&&!fine_idle_study)EnableWindow(slider[8],FALSE);
    if(catalog_mode)EnableWindow(slider[8],!locked&&dc_aux_enabled(cap,auxiliary_index));
    for(i=0;i<2;++i)EnableWindow(slider[i],!locked&&c.drive.mode!=VSL_BENCH);
    EnableWindow(slider[2],!locked&&c.drive.mode==VSL_BENCH);
    EnableWindow(gear,!locked&&c.drive.mode!=VSL_BENCH);
    EnableWindow(slider[4],!locked&&c.mix.spatial);EnableWindow(slider[5],!locked&&c.mix.spatial);
    EnableWindow(voice,!playing&&(catalog_mode||!resonant_study)&&
        !(catalog_mode&&audio.transport==1&&InterlockedCompareExchange(&audio.device.running,0,0)));EnableWindow(mode,!locked);
    EnableWindow(GetDlgItem(owner,12),!locked);EnableWindow(GetDlgItem(owner,30),!locked);EnableWindow(GetDlgItem(owner,31),!locked);
    EnableWindow(GetDlgItem(owner,14),audio.ready||audio.transport==1);
    if(audio.transport==2||catalog_mode) {
        int values[8]={(int)(c.drive.throttle*100),(int)(c.drive.brake*100),(int)c.drive.rpm,
            (int)(20*log10(fmax(1e-12,c.mix.gain/.5))),(int)(c.mix.width*100),(int)(c.mix.room*100),
            (int)((resonant_study?c.mix.resonant_gain:c.mix.residual_gain)*100),
            (int)((resonant_study==3?c.mix.coherent_low_gain:c.mix.body_mix)*100)};
        for(i=0;i<8;++i)SendMessageW(slider[i],TBM_SETPOS,TRUE,values[i]);
        SendMessageW(mode,CB_SETCURSEL,c.drive.mode==VSL_BENCH?1:0,0);
        SendMessageW(gear,CB_SETCURSEL,c.drive.automatic?0:c.drive.gear+1,0);
    }
    SendMessageW(voice,CB_SETCURSEL,catalog_mode?(audio.transport==2?DC_COUNT:dc_preset_selection(catalog.preset)):playing?(catch_study?3:2):resonant_study?0:bank_index,0);
    SendMessageW(GetDlgItem(owner,30),BM_SETCHECK,c.mix.spatial?BST_CHECKED:BST_UNCHECKED,0);
    SendMessageW(GetDlgItem(owner,31),BM_SETCHECK,c.mix.event_gain>0?BST_CHECKED:BST_UNCHECKED,0);
    if(idle_study&&!catalog_mode)SendMessageW(GetDlgItem(owner,31),BM_SETCHECK,c.mix.idle_mix>0?BST_CHECKED:BST_UNCHECKED,0);
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
    else if(index==6){if(resonant_study)c.mix.resonant_gain=value/100.;else c.mix.residual_gain=value/100.;}
    else if(index==7){if(resonant_study==3)c.mix.coherent_low_gain=value/100.;else c.mix.body_mix=value/100.;}
    else if(index==8)*aux_amount(&c,auxiliary_index)=value/100.;
    am_audio_control(&audio,&c);labels(owner);
}
static int load_bank(int index) {
    if(resonant_study)return index==0;
    AmModels *candidate=malloc(sizeof *candidate);int ok=0;
    if(candidate&&am_models_load_variant(candidate,index,startup_detail_study)) {
        am_audio_stop(&audio);models=*candidate;
        /* Rebind borrowed pointers to committed storage, never the candidate. */
        if(am_models_bank(&models,&bank)){
            AdControl c=am_audio_get(&audio);c.mix.startup_gain=0;c.mix.catch_gain=0;
            if(!models.residual.count)c.mix.residual_gain=0;
            audio.config.residual_bank=models.residual.count?&models.residual:NULL;
            audio.config.root_per_rpm=index==2?models.profile[0].base_hz/vsl_profile(VSL_V10)->idle_rpm:1./120;
            audio.config.startup_profile=startup_study&&(index==1||index==2)?&startup_profile:NULL;
            audio.config.catch_profile=catch_study&&index==2?&catch_profile:NULL;
            am_audio_control(&audio,&c);bank_index=index;ok=1;
        }
    }
    free(candidate);return ok;
}
static int catalog_select(HWND owner,int index) {
    DcPreset *candidate=cd_models_load(index);
    if(!candidate)return 0;
    if(!am_take_preserve(owner,&audio)||!cd_session_commit(&catalog,&audio,candidate)) {dc_preset_destroy(candidate);return 0;}
    auxiliary_index=audio.config.fine_idle_profile?DC_IDLE:audio.config.startup_profile?DC_STARTUP:DC_INTAKE;
    SendMessageW(auxiliary,CB_SETCURSEL,auxiliary_index,0);labels(owner);return 1;
}
static LRESULT CALLBACK procedure(HWND owner,UINT message,WPARAM w,LPARAM l) {
    switch(message) {
    case WM_CREATE: {
        int i;
        font=CreateFontW(-17,0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        heading=CreateFontW(-24,0,0,0,FW_SEMIBOLD,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
        SendMessageW(item(owner,L"STATIC",L"DNA 驾驶监听",0,0,24,18,510,36),WM_SETFONT,(WPARAM)heading,TRUE);
        voice=item(owner,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP,40,24,65,510,160);
        if(catalog_mode)for(i=0;i<DC_COUNT;++i){wchar_t name[160];MultiByteToWideChar(CP_UTF8,0,dc_info(i)->title,-1,name,160);SendMessageW(voice,CB_ADDSTRING,0,(LPARAM)name);}
        else {
        SendMessageW(voice,CB_ADDSTRING,0,(LPARAM)(resonant_study==3?L"V10 · 行驶35%完整配方（局部）":resonant_study==2?L"V10 · 启动趋稳双声道（实验）":resonant_study?L"V10 · 车外局部细节（实验）":L"V10 · 驻车车外四档（实验）"));
        SendMessageW(voice,CB_ADDSTRING,0,(LPARAM)L"V10 · 高转车内两档（实验）");SendMessageW(voice,CB_SETCURSEL,0,0);
        if(catch_study)SendMessageW(voice,CB_ADDSTRING,0,(LPARAM)L"V10 · 启动车内趋稳（实验）");
        }
        SendMessageW(voice,CB_ADDSTRING,0,(LPARAM)L"行程内嵌音色（回放）");
        mode=item(owner,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP,41,24,108,245,150);
        SendMessageW(mode,CB_ADDSTRING,0,(LPARAM)L"模拟驾驶");SendMessageW(mode,CB_ADDSTRING,0,(LPARAM)L"转速台架");SendMessageW(mode,CB_SETCURSEL,0,0);
        if(catch_study||resonant_study)SendMessageW(mode,CB_SETCURSEL,1,0);
        gear=item(owner,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP,42,289,108,245,270);
        SendMessageW(gear,CB_ADDSTRING,0,(LPARAM)L"自动挡 · 运动");SendMessageW(gear,CB_ADDSTRING,0,(LPARAM)L"空挡 N");
        for(i=1;i<=7;++i){wchar_t text[32];swprintf(text,32,L"手动 %d 挡",i);SendMessageW(gear,CB_ADDSTRING,0,(LPARAM)text);}
        SendMessageW(gear,CB_SETCURSEL,0,0);
        telemetry=item(owner,L"STATIC",L"0 RPM    0.0 km/h    N",0,60,24,153,245,32);
        listen_choice=item(owner,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP,44,289,153,245,240);
        {static const wchar_t *names[]={L"完整混音",L"DNA · 干声",L"低频 · 干声",L"细节 · 干声",L"辅助 · 干声",L"启停／事件 · 干声",L"其他声源 · 干声"};
            for(i=0;i<LM_SELECTIONS;++i)SendMessageW(listen_choice,CB_ADDSTRING,0,(LPARAM)names[i]);
            SendMessageW(listen_choice,CB_SETCURSEL,0,0);}
        for(i=0;i<9;++i) {
            int y=194+52*i;
            label[i]=item(owner,L"STATIC",L"",0,70+i,24,y,i==8?240:510,25);
            slider[i]=item(owner,TRACKBAR_CLASSW,L"",TBS_HORZ|TBS_NOTICKS|WS_TABSTOP,20+i,24,y+24,510,28);
            SendMessageW(slider[i],TBM_SETRANGEMIN,FALSE,minimum[i]);SendMessageW(slider[i],TBM_SETRANGEMAX,TRUE,maximum[i]);
            SendMessageW(slider[i],TBM_SETPOS,TRUE,initial[i]);
        }
        if(catch_study||resonant_study) {
            AdControl c=am_audio_get(&audio);
            SendMessageW(slider[2],TBM_SETPOS,TRUE,(int)c.drive.rpm);
            SendMessageW(slider[4],TBM_SETPOS,TRUE,(int)(100*c.mix.width));
        }
        auxiliary=item(owner,WC_COMBOBOXW,L"",CBS_DROPDOWNLIST|WS_TABSTOP,43,276,610,258,180);
        if(catalog_mode)for(i=0;i<DC_AUX_COUNT;++i){wchar_t name[80];MultiByteToWideChar(CP_UTF8,0,dc_aux_name(i),-1,name,80);SendMessageW(auxiliary,CB_ADDSTRING,0,(LPARAM)name);}
        else {
        SendMessageW(auxiliary,CB_ADDSTRING,0,(LPARAM)L"进气");SendMessageW(auxiliary,CB_ADDSTRING,0,(LPARAM)L"机械");
        SendMessageW(auxiliary,CB_ADDSTRING,0,(LPARAM)L"排气空气");SendMessageW(auxiliary,CB_ADDSTRING,0,(LPARAM)L"道路");
        SendMessageW(auxiliary,CB_ADDSTRING,0,(LPARAM)L"风");SendMessageW(auxiliary,CB_SETCURSEL,0,0);
        if(startup_study)SendMessageW(auxiliary,CB_ADDSTRING,0,(LPARAM)L"启动机械声");
        if(idle_study){SendMessageW(auxiliary,CB_ADDSTRING,0,(LPARAM)L"怠速声线（候选）");SendMessageW(auxiliary,CB_SETCURSEL,5,0);}
        if(fine_idle_study){SendMessageW(auxiliary,CB_ADDSTRING,0,(LPARAM)L"怠速主声线起伏");SendMessageW(auxiliary,CB_ADDSTRING,0,(LPARAM)L"怠速细谱纹理");}
        if(catch_study){SendMessageW(auxiliary,CB_ADDSTRING,0,(LPARAM)L"接火低频");SendMessageW(auxiliary,CB_SETCURSEL,6,0);}
        }
        if(catalog_mode)SendMessageW(auxiliary,CB_SETCURSEL,auxiliary_index,0);
        item(owner,L"BUTTON",L"空间监听",BS_AUTOCHECKBOX|WS_TABSTOP,30,24,670,210,28);
        item(owner,L"BUTTON",idle_study&&!catalog_mode?L"怠速声线（候选）":L"瞬态层（实验）",BS_AUTOCHECKBOX|WS_TABSTOP,31,276,670,240,28);
        item(owner,L"BUTTON",L"开始／重新监听",BS_PUSHBUTTON|WS_TABSTOP,10,24,712,204,40);
        item(owner,L"BUTTON",L"点火",BS_PUSHBUTTON|WS_TABSTOP,12,244,712,134,40);
        item(owner,L"BUTTON",L"停止",BS_PUSHBUTTON|WS_TABSTOP,11,394,712,140,40);
        item(owner,L"BUTTON",L"录制完整行程",BS_PUSHBUTTON|WS_TABSTOP,13,24,764,158,36);
        item(owner,L"BUTTON",L"保存行程",BS_PUSHBUTTON|WS_TABSTOP,14,194,764,158,36);
        item(owner,L"BUTTON",L"载入回放",BS_PUSHBUTTON|WS_TABSTOP,15,364,764,170,36);
        status=item(owner,L"STATIC",L"已停止 · 先开始监听，再点火",0,61,24,813,510,30);
        item(owner,L"STATIC",L"分层只影响监听 · 行程保存完整混音",0,0,24,854,510,27);
        labels(owner);SetTimer(owner,1,40,NULL);return 0;
    }
    case WM_HSCROLL: {
        int id=GetDlgCtrlID((HWND)l);if(id>=20&&id<29)changed(owner,id-20);return 0;
    }
    case WM_COMMAND: {
        AdControl c=am_audio_get(&audio);int id=LOWORD(w),notify=HIWORD(w);
        if(id==10) {
            if(am_take_preserve(owner,&audio)&&(!catalog_mode||cd_session_restore(&catalog,&audio))&&!am_audio_start(&audio,muted,0))SetWindowTextW(status,L"无法开始监听");labels(owner);return 0;
        }
        if(id==11){am_take_preserve(owner,&audio);labels(owner);return 0;}
        if(id==13){if(!catalog_mode||(am_take_preserve(owner,&audio)&&cd_session_restore(&catalog,&audio)))am_take_record(owner,&audio,muted);labels(owner);return 0;}
        if(id==14){am_take_save_dialog(owner,&audio);labels(owner);return 0;}
        if(id==15){if(catalog_mode)cd_session_before_replay(&catalog,&audio);am_take_load_dialog(owner,&audio,muted);labels(owner);return 0;}
        if(id==12) {
            c.drive.ignition=!c.drive.ignition;
            if(c.drive.ignition)++c.drive.start_id;
            am_audio_control(&audio,&c);labels(owner);return 0;
        }
        if(id==30||id==31) {
            int on=SendMessageW(GetDlgItem(owner,id),BM_GETCHECK,0,0)==BST_CHECKED;
            if(id==30)c.mix.spatial=on;else if(idle_study&&!catalog_mode)c.mix.idle_mix=on?1:0;else c.mix.event_gain=on?.3:0;
            am_audio_control(&audio,&c);labels(owner);return 0;
        }
        if(id==40&&notify==CBN_SELCHANGE) {
            int index=(int)SendMessageW(voice,CB_GETCURSEL,0,0);
            if(catalog_mode){if(!catalog_select(owner,index))labels(owner);return 0;}
            if(index>(catch_study?2:1)||!am_take_preserve(owner,&audio)||!load_bank(index))SendMessageW(voice,CB_SETCURSEL,bank_index,0);
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
        if(id==43&&notify==CBN_SELCHANGE) {
            int selected=(int)SendMessageW(auxiliary,CB_GETCURSEL,0,0);
            if(selected>=0&&selected<(catalog_mode?DC_AUX_COUNT:fine_idle_study?8:catch_study?7:startup_study||idle_study?6:5))auxiliary_index=selected;
            labels(owner);return 0;
        }
        if(id==44&&notify==CBN_SELCHANGE) {
            am_audio_listen_set(&audio,(int)SendMessageW(listen_choice,CB_GETCURSEL,0,0));return 0;
        }
        break;
    }
    case WM_TIMER: {
        catalog_flags();
        WoStats s=wo_stats(&audio.device);AdTelemetry t=am_audio_latest(&audio);wchar_t text[180],g[16];
        if(t.gear>0)swprintf(g,16,L"%d 挡",t.gear);else wcscpy_s(g,16,L"N");
        if(am_audio_get(&audio).drive.mode==VSL_BENCH)swprintf(text,180,L"%.0f RPM    转速台架",t.rpm);
        else swprintf(text,180,L"%.0f RPM    %.1f km/h    %ls",t.rpm,t.speed,g);
        if(resonant_study)swprintf(text,180,L"%.0f RPM    细节启用范围 %.0f%%",t.rpm,100*t.resonant_support);
        if(idle_study)swprintf(text,180,L"%.0f RPM    怠速声线 %.0f%%",t.rpm,100*t.idle_weight);
        SetWindowTextW(telemetry,text);
        labels(owner);
        if(s.error[0])SetWindowTextW(status,s.error);
        else if(InterlockedCompareExchange(&audio.device.running,0,0)) {
            swprintf(text,180,L"%ls · %.1f 秒%ls",audio.transport==2?L"回放中":audio.transport==1?L"录制中":L"监听中",s.frames/48000.,
                t.coverage?L" · 超出录音音高范围":L"");SetWindowTextW(status,text);
        } else {
            if(audio.transport==1){am_take_preserve(owner,&audio);audio.transport=0;}
            LONG result=InterlockedCompareExchange(&audio.replay_result,0,0);
            SetWindowTextW(status,audio.transport==2?(result==1?L"回放完成 · 一致性校验通过":result==2?L"回放已停止":L"回放校验失败"):
                audio.ready?L"已停止 · 行程可保存／回放":L"已停止 · 先开始监听，再点火");
        }
        return 0;
    }
    case WM_CTLCOLORSTATIC:SetBkMode((HDC)w,TRANSPARENT);return (LRESULT)GetSysColorBrush(COLOR_WINDOW);
    case WM_CLOSE:if(am_take_preserve(owner,&audio))DestroyWindow(owner);return 0;
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
    for(i=1;i<argc;++i)if(!wcscmp(args[i],L"--muted"))muted=1;
        else if(!wcscmp(args[i],L"--catalog"))catalog_mode=1;
        else if(!wcscmp(args[i],L"--stereo-bed"))config.scene_mode=AD_SCENE_STEREO_BED;
        else if(!wcscmp(args[i],L"--startup-study"))startup_study=1;
        else if(!wcscmp(args[i],L"--catch-study")){catch_study=1;startup_study=1;}
        else if(!wcscmp(args[i],L"--startup-detail-study")){startup_detail_study=1;catch_study=1;startup_study=1;}
        else if(!wcscmp(args[i],L"--resonant-study"))resonant_study=1;
        else if(!wcscmp(args[i],L"--stereo-resonant-study"))resonant_study=2;
        else if(!wcscmp(args[i],L"--full-recipe-study"))resonant_study=3;
        else if(!wcscmp(args[i],L"--idle-study")){idle_study=1;resonant_study=3;}
        else if(!wcscmp(args[i],L"--fine-idle-study")){fine_idle_study=idle_study=1;resonant_study=3;}
        else if(!wcscmp(args[i],L"--ui-check")&&i+1<argc) {
            if(wcslen(args[i+1])>=4096){LocalFree(args);return 2;}wcscpy_s(ui_check_path,4096,args[++i]);
        }
        else{LocalFree(args);return 2;}
    LocalFree(args);
    if(catalog_mode&&(resonant_study||startup_study||idle_study))return 2;
    if(resonant_study&&startup_study)return 2;
    if(idle_study&&resonant_study!=3)return 2;
    bank_index=resonant_study==2?2:catch_study?2:startup_study?1:0;
    if(!project_directory())return 2;
    if(catalog_mode) {
        catalog.preset=cd_models_load(DC_FINE_IDLE);if(!catalog.preset)return 2;
        config=*dc_preset_config(catalog.preset);catalog.live=dc_preset_initial(catalog.preset);
        am_audio_init(&audio,&config);am_audio_control(&audio,&catalog.live);auxiliary_index=DC_IDLE;catalog_flags();
    }else {
    if(resonant_study==3) {
        if(!fr_models_load(&full_recipe))return 2;
        config.bank=&full_recipe.bank;config.recipe_bank=&full_recipe.recipe;
    } else if(!am_models_load_variant(&models,bank_index,startup_detail_study)||!am_models_bank(&models,&bank))return 2;
    if(startup_study){if(!am_startup_load(&startup_profile))return 2;config.startup_profile=&startup_profile;config.scene_mode=AD_SCENE_STEREO_BED;}
    if(catch_study) {
        if(!am_catch_load(&catch_profile))return 2;config.catch_profile=&catch_profile;
        config.residual_bank=models.residual.count?&models.residual:NULL;
        config.root_per_rpm=models.profile[0].base_hz/vsl_profile(VSL_V10)->idle_rpm;auxiliary_index=6;
    }
    if(resonant_study) {
        const RdtProfile *detail[SA_MAX_ANCHORS]={&resonant_profile};
        if(resonant_study==3) {
            config.resonant_bank=&full_recipe.resonance;
        } else if(resonant_study==2) {
            const RvsProfile *stereo[SA_MAX_ANCHORS]={&stereo_profile};
            if(!rvs_profile_load("voices/stereo_resonance_v1/A cabin settle.sres",&stereo_profile)||!drs_bank_init_stereo(&resonant_bank,&bank,stereo))return 2;
            config.root_per_rpm=models.profile[0].base_hz/vsl_profile(VSL_V10)->idle_rpm;
        } else if(!rdt_profile_load("voices/resonant_detail_c_v1/idle_add.rdetail",&resonant_profile)||!drs_bank_init(&resonant_bank,&bank,detail))return 2;
        if(resonant_study!=3)config.resonant_bank=&resonant_bank;
        config.residual_bank=NULL;config.scene_mode=AD_SCENE_STEREO_BED;
    }
    if(fine_idle_study){if(!fid_models_load(&fine_idle_models))return 2;config.fine_idle_profile=&fine_idle_models.idle;auxiliary_index=5;}
    else if(idle_study){if(!id_models_load(&idle_models))return 2;config.idle_profile=&idle_models.idle;auxiliary_index=5;}
    am_audio_init(&audio,&config);InitCommonControlsEx(&common);
    if(startup_study){AdControl c=am_audio_get(&audio);c.mix.startup_gain=.5;am_audio_control(&audio,&c);}
    if(catch_study) {
        AdControl c=am_audio_get(&audio);c.drive.mode=VSL_BENCH;c.drive.rpm=vsl_profile(VSL_V10)->idle_rpm;
        c.mix.width=1;c.mix.spatial=1;am_audio_control(&audio,&c);
    }
    if(startup_detail_study){AdControl c=am_audio_get(&audio);c.mix.catch_gain=.5;am_audio_control(&audio,&c);}
    if(resonant_study){AdControl c=am_audio_get(&audio);c.drive.mode=VSL_BENCH;
        c.drive.rpm=(resonant_study==3?full_recipe.dna.base_hz:resonant_study==2?stereo_profile.base_hz:resonant_profile.base_hz)/config.root_per_rpm;
        if(resonant_study==3){c.mix.resonant_gain=1;c.mix.coherent_low_gain=1;}
        c.mix.width=1;am_audio_control(&audio,&c);}
    if(idle_study){AdControl c=am_audio_get(&audio);c.drive.rpm=850;c.drive.load=0;c.mix.idle_mix=1;am_audio_control(&audio,&c);}
    if(fine_idle_study){AdControl c=am_audio_get(&audio);c.mix.idle_motion=.5;c.mix.idle_detail=1;am_audio_control(&audio,&c);}
    }
    InitCommonControlsEx(&common);
    SetProcessDPIAware();klass.lpfnWndProc=procedure;klass.hInstance=instance;klass.lpszClassName=L"VslAtlasMonitor";
    klass.hCursor=LoadCursorW(NULL,IDC_ARROW);klass.hbrBackground=GetSysColorBrush(COLOR_WINDOW);
    if(!RegisterClassW(&klass)){am_audio_destroy(&audio);cd_session_dispose(&catalog);return 2;}
    window=CreateWindowW(klass.lpszClassName,catalog_mode?L"Vehicle Sound Lab · DNA Drive · Voice Catalog":fine_idle_study?L"Vehicle Sound Lab · DNA Drive · Fine Idle":idle_study?L"Vehicle Sound Lab · DNA Drive · Idle Candidate":resonant_study==3?L"Vehicle Sound Lab · DNA Drive · Full Recipe":resonant_study==2?L"Vehicle Sound Lab · DNA Drive · Stereo Detail":resonant_study?L"Vehicle Sound Lab · DNA Drive · Resonant Detail":startup_detail_study?L"Vehicle Sound Lab · DNA Drive · Startup Detail Study":catch_study?L"Vehicle Sound Lab · DNA Drive · Catch Study":startup_study?L"Vehicle Sound Lab · DNA Drive · Startup Study":config.scene_mode==AD_SCENE_STEREO_BED?L"Vehicle Sound Lab · DNA Drive · Stereo Bed":L"Vehicle Sound Lab · DNA Drive",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,
        CW_USEDEFAULT,CW_USEDEFAULT,580,936,NULL,NULL,instance,NULL);
    if(!window){am_audio_destroy(&audio);cd_session_dispose(&catalog);return 2;}
    if(ui_check_path[0]) {
        int ok=catalog_mode?cd_ui_check(window,&audio,&catalog,ui_check_path):resonant_study?am_resonant_ui_check(window,&audio,ui_check_path):am_startup_detail_ui_check(window,&audio,&models,startup_detail_study,ui_check_path);
        DestroyWindow(window);am_audio_destroy(&audio);cd_session_dispose(&catalog);return ok?0:3;
    }
    ShowWindow(window,show);UpdateWindow(window);
    while(GetMessageW(&message,NULL,0,0)>0)if(!IsDialogMessageW(window,&message)){TranslateMessage(&message);DispatchMessageW(&message);}
    am_audio_destroy(&audio);cd_session_dispose(&catalog);return (int)message.wParam;
}

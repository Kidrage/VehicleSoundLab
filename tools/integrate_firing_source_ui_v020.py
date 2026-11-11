"""One-time native control/persistence/device-test integration for DSP020."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
files={}
def change(name,old,new):
    text=files.get(name,(ROOT/name).read_text(encoding='utf-8'))
    if text.count(old)!=1: raise ValueError((name,old[:100],text.count(old)))
    files[name]=text.replace(old,new)
def main():
    change('src/app/audio_device.h','    uint64_t event_color_events;','    uint64_t event_color_events;\n    double pulse_mix;uint64_t pulse_events;unsigned pulse_overflow;')
    change('src/app/audio_device.c','                a->event_color_events=a->engine->color.events[0]+a->engine->color.events[1];','                a->event_color_events=a->engine->color.events[0]+a->engine->color.events[1];\n                a->pulse_mix=a->engine->firing_source.mix;\n                a->pulse_events=a->engine->firing_source.accepted[0]+a->engine->firing_source.accepted[1];\n                a->pulse_overflow=a->engine->firing_source.kernel.overflow;')
    change('src/app/main.c','static int smoke_color_control,smoke_color_preset,smoke_color_legacy,smoke_color_active;','static int smoke_color_control,smoke_color_preset,smoke_color_legacy,smoke_color_active;\nstatic int smoke_pulse_control,smoke_pulse_preset,smoke_pulse_legacy,smoke_pulse_active;')
    change('src/app/main.c','params.response_shape=.613456789123456;params.event_color=.543456789123456;','params.response_shape=.613456789123456;params.event_color=.543456789123456;\n                params.firing_source=VSL_SOURCE_VARIABLE;params.pulse_amount=.713456789123456;')
    change('src/app/main.c','params.event_color=.783456789123456;slider_values();','params.event_color=.783456789123456;params.firing_source=VSL_SOURCE_FIXED;params.pulse_amount=.893456789123456;slider_values();')
    change('src/app/main.c','                smoke_color_active=audio.event_color_mix>.4&&audio.event_color_events>100&&audio.event_color_max_mod>.05;','                smoke_color_active=audio.event_color_mix>.4&&audio.event_color_events>100&&audio.event_color_max_mod>.05;\n                smoke_pulse_active=audio.pulse_mix>.8&&audio.pulse_events>100&&audio.pulse_overflow==0;')
    marker='                    params=saved;\n                    SendMessageW(sliders[7]'
    tests='''                    {
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
'''
    change('src/app/main.c',marker,tests+marker)
    change('src/app/main.c','                    fprintf(f,"\\\"event_color_control\\\":%s,','                    fprintf(f,"\\\"pulse_controls\\\":%s,\\\"pulse_preset_roundtrip\\\":%s,\\\"pulse_legacy_preset\\\":%s,\\\"pulse_active_on_device\\\":%s,",smoke_pulse_control?"true":"false",smoke_pulse_preset?"true":"false",smoke_pulse_legacy?"true":"false",smoke_pulse_active?"true":"false");\n                    fprintf(f,"\\\"event_color_control\\\":%s,')
    change('src/app/main.c','                        locked=!IsWindowEnabled(detail)','                        SendMessageW(GetDlgItem(detail,111),TBM_SETPOS,TRUE,123);\n                        SendMessageW(detail,WM_HSCROLL,0,(LPARAM)GetDlgItem(detail,111));\n                        SendMessageW(GetDlgItem(detail,110),CB_SETCURSEL,VSL_SOURCE_VARIABLE,0);\n                        SendMessageW(detail,WM_COMMAND,MAKEWPARAM(110,CBN_SELCHANGE),(LPARAM)GetDlgItem(detail,110));\n                        locked=!IsWindowEnabled(detail)')
    change('src/app/take_smoke.c','    VslEventColor expected_color=a->engine->color;int color_state=0,device_color=0;','    VslEventColor expected_color=a->engine->color;int color_state=0,device_color=0;\n    VslFiringSource expected_pulse=a->engine->firing_source;int pulse_state=0,device_pulse=0;')
    change('src/app/take_smoke.c','        color_state=!memcmp(&expected_color,&e->color,sizeof expected_color);','        color_state=!memcmp(&expected_color,&e->color,sizeof expected_color);\n        pulse_state=!memcmp(&expected_pulse,&e->firing_source,sizeof expected_pulse);')
    change('src/app/take_smoke.c','        device_color=!memcmp(&expected_color,&a->engine->color,sizeof expected_color);','        device_color=!memcmp(&expected_color,&a->engine->color,sizeof expected_color);\n        device_pulse=!memcmp(&expected_pulse,&a->engine->firing_source,sizeof expected_pulse);')
    change('src/app/take_smoke.c','\\\"result\\\":",character_state,device_character,response_state,device_response,color_state,device_color);','\\\"pulse_state_match\\\":%d,\\\"device_pulse_state_match\\\":%d,\\\"result\\\":",character_state,device_character,response_state,device_response,color_state,device_color,pulse_state,device_pulse);')
    change('tests/test_take.c','p.event_color=.571234567891234;','p.event_color=.571234567891234;p.firing_source=VSL_SOURCE_VARIABLE;p.pulse_amount=.723456789123;')
    change('tests/test_take.c','p.event_color=.891234567891234;','p.event_color=.891234567891234;p.firing_source=VSL_SOURCE_FIXED;p.pulse_amount=.393456789123;')
    change('tests/test_take.c','p.mechanical_model=0;p.response_shape=0;p.event_color=0;','p.mechanical_model=0;p.response_shape=0;p.event_color=0;p.firing_source=VSL_SOURCE_OSC;')
    change('tests/test_take.c','"fields 36","fields 35"','"fields 38","fields 36"')
    change('tests/test_take.c','"VSLTAKE 4","VSLTAKE 3"','"VSLTAKE 5","VSLTAKE 4"')
    change('tests/test_take.c','    CHECK(!vsl_take_begin(&t,e),','    CHECK(!memcmp(&e->firing_source,&r->firing_source,sizeof e->firing_source),"complete event source reconstruction");\n    CHECK(!memcmp(&r->firing_source,&m->firing_source,sizeof r->firing_source),"event source layout independence");\n    CHECK(!vsl_take_begin(&t,e),')
    change('tests/test_take.c','    t.events[0].params.propagation=2;','    t.events[0].params.firing_source=3;CHECK(!vsl_take_validate(&t),"invalid event-source enum rejected");t.events[0].params.firing_source=0;\n    t.events[0].params.pulse_amount=NAN;CHECK(!vsl_take_validate(&t),"nonfinite pulse mix rejected");t.events[0].params.pulse_amount=1;\n    t.events[0].params.propagation=2;')
    for name,text in files.items():(ROOT/name).write_text(text,encoding='utf-8')
    print('DSP020 native UI/device checks and strict schema5/38 fields integrated.')
if __name__=='__main__':main()

"""One-time, prevalidated native integration of the frozen main-pressure candidate."""
import json
from runtime_review import ROOT,sha


def main():
    frozen=json.loads((ROOT/'baselines/v0.18.0/manifest.json').read_text(encoding='utf-8'))
    for item in frozen['files']:
        if item['path'].startswith(('src/','tests/')):
            assert sha(ROOT/item['path'])==item['sha256'],item['path']
    files={}
    def change(name,old,new):
        text=files.get(name,(ROOT/name).read_text(encoding='utf-8'))
        assert text.count(old)==1,(name,old)
        files[name]=text.replace(old,new)
    def add(name,text):
        assert not (ROOT/name).exists(),name
        files[name]=text
    experiment=ROOT/'baselines/event_color_v1/experiments/event_color_v1'
    for source,target in [('split.h','src/core/event_split.h'),('split.c','src/core/event_split.c'),
        ('profile.h','src/profiles/event_color.h'),('profile.c','src/profiles/event_color.c'),('color.c','src/core/event_color.c')]:
        text=(experiment/source).read_text(encoding='utf-8')
        text=text.replace('"split.h"','"core/event_split.h"').replace('"profile.h"','"profiles/event_color.h"').replace('"color.h"','"core/event_color.h"')
        if source=='color.c':
            observer='    if(s->tap_samples&&s->tap_frames<s->tap_capacity) {\n        memcpy(s->tap_samples+s->tap_frames*8,s->last,sizeof s->last);++s->tap_frames;\n    }\n'
            assert text.count(observer)==1;text=text.replace(observer,'')
        add(target,text)
    header=(experiment/'color.h').read_text(encoding='utf-8')
    state=header[header.index('typedef struct {'):header.index('int vsl_color_init')]
    observer='    /* Optional offline double-precision observer; no allocation or file I/O. */\n    double *tap_samples;uint64_t tap_frames,tap_capacity;\n'
    assert state.count(observer)==1;state=state.replace(observer,'')
    add('src/core/event_color_types.h','#ifndef VSL_EVENT_COLOR_TYPES_H\n#define VSL_EVENT_COLOR_TYPES_H\n#include "event_split.h"\n#include <stdint.h>\n'+state+'#endif\n')
    declarations=header[header.index('int vsl_color_init'):header.index('int vsl_color_process')]
    add('src/core/event_color.h','#ifndef VSL_EVENT_COLOR_H\n#define VSL_EVENT_COLOR_H\n#include "engine.h"\n'+declarations+'#endif\n')
    change('src/core/types.h','#define VSL_VERSION "0.18.0"','#define VSL_VERSION "0.19.0"')
    change('src/core/types.h','#include "response_types.h"','#include "response_types.h"\n#include "event_color_types.h"')
    change('src/core/types.h','double pressure_texture,structure_transfer,response_shape;','double pressure_texture,structure_transfer,response_shape,event_color;')
    change('src/core/types.h','    VslResponseShape response;','    VslResponseShape response;\n    VslEventColor color;')
    change('src/core/character.c','#include "response_shape.h"','#include "response_shape.h"\n#include "event_color.h"')
    change('src/core/character.c','    vsl_response_init(&e->response,e->sample_rate,0);',
        '    vsl_response_init(&e->response,e->sample_rate,0);\n    vsl_color_init(&e->color,e->sample_rate,0);')
    change('src/core/engine.c','#include "character.h"','#include "character.h"\n#include "event_color.h"')
    change('src/core/engine.c','UNIT(response_shape);','UNIT(response_shape);UNIT(event_color);')
    change('src/core/engine.c','FOLLOW(response_shape);','FOLLOW(response_shape);FOLLOW(event_color);')
    change('src/core/engine.c','double l,r,bed,event,spatial[VSL_MAX_CHANNELS],ir;',
        'double l,r,bed,event,spatial[VSL_MAX_CHANNELS],ir,main_pressure[2];')
    change('src/core/engine.c','vsl_high_orders_tick(e,o);vsl_excitation_tick(e,o);',
        'vsl_high_orders_tick(e,o);main_pressure[0]=o->sample[0];main_pressure[1]=o->sample[1];vsl_excitation_tick(e,o);')
    change('src/core/engine.c','        vsl_character_tick(e,o);',
        '        vsl_character_tick(e,o);\n        e->color.amount=e->smooth.event_color;vsl_color_tick(&e->color,e,o,main_pressure);')
    change('src/core/profiles.c','    p.response_shape=0;', '    p.event_color=0; /* Optional main-pressure control, absent in old presets. */\n    p.response_shape=0;')
    change('CMakeLists.txt','VERSION 0.18.0','VERSION 0.19.0')
    change('CMakeLists.txt','  src/core/response_kernel.c src/core/response_shape.c src/profiles/response_shape.c',
        '  src/core/response_kernel.c src/core/response_shape.c src/profiles/response_shape.c\n  src/core/event_split.c src/core/event_color.c src/profiles/event_color.c')
    change('CMakeLists.txt','enable_testing()',
        'enable_testing()\nadd_executable(vsl_event_color_tests tests/test_event_color.c)\ntarget_link_libraries(vsl_event_color_tests PRIVATE vsl_core)\nadd_test(NAME live_main_pressure_color COMMAND vsl_event_color_tests)')
    change('src/session/parameters.h','D(structure_transfer) D(response_shape)','D(structure_transfer) D(response_shape) D(event_color)')
    change('src/io/take_file.c','VSLTAKE 3\\n','VSLTAKE 4\\n')
    change('src/io/take_file.c','!word(f,"VSLTAKE")||!word(f,"3")','!word(f,"VSLTAKE")||!word(f,"4")')
    change('src/io/scene_metadata.c','FIELD(response_shape);','FIELD(response_shape);FIELD(event_color);')
    change('src/io/drive_trace.c','    fputc(\'\\n\',f);\n}\nvoid vsl_trace_frame',
        '    fputs(",event_color_target,event_color_mix,event_color_events_l,event_color_events_r,event_color_max_mod",f);\n    fputc(\'\\n\',f);\n}\nvoid vsl_trace_frame')
    name='src/io/drive_trace.c';text=files[name];i=text.rindex("    fputc('\\n',f);")
    files[name]=text[:i]+'    fprintf(f,",%.12g,%.12g,%llu,%llu,%.12g",e->target.event_color,e->color.amount,\n        (unsigned long long)e->color.events[0],(unsigned long long)e->color.events[1],e->color.max_mod);\n'+text[i:]
    change('src/app/preset.c','D(response_shape)}','D(response_shape),D(event_color)}')
    change('src/app/tuning.c','character_sliders[3],character_labels[3]','character_sliders[4],character_labels[4]')
    change('src/app/tuning.c','SetWindowTextW(character_labels[2],text); }',
        'SetWindowTextW(character_labels[2],text);\n      swprintf(text,100,L"Main pressure shape (test)    %.0f%%",params->event_color*100);SetWindowTextW(character_labels[3],text); }')
    change('src/app/tuning.c','for(i=0;i<3;++i) {\n            int x=20+(i%2)*320','for(i=0;i<4;++i) {\n            int x=20+(i%2)*320')
    change('src/app/tuning.c','        label_values();SendMessageW(owner,VSL_TUNING_CHANGED,0,0);return 0;',
        '        if((HWND)l==character_sliders[3])params->event_color=SendMessageW(character_sliders[3],TBM_GETPOS,0,0)/1000.;\n        label_values();SendMessageW(owner,VSL_TUNING_CHANGED,0,0);return 0;')
    change('src/app/tuning.c','    Button_SetCheck(fuel_switch,params->fuel_cut);',
        '    SendMessageW(character_sliders[3],TBM_SETPOS,TRUE,(LPARAM)(params->event_color*1000));\n    Button_SetCheck(fuel_switch,params->fuel_cut);')
    change('src/app/audio_device.h','    uint64_t response_pressure_events;',
        '    uint64_t response_pressure_events;\n    double event_color_mix,event_color_max_mod;\n    uint64_t event_color_events;')
    change('src/app/audio_device.c','                a->response_pressure_events=a->engine->response.pressure_events;',
        '                a->response_pressure_events=a->engine->response.pressure_events;\n                a->event_color_mix=a->engine->color.amount;a->event_color_max_mod=a->engine->color.max_mod;\n                a->event_color_events=a->engine->color.events[0]+a->engine->color.events[1];')
    for name in ['src/app/main.c','src/app/take_smoke.c']:
        files[name]=(ROOT/name).read_text(encoding='utf-8').replace('v0.18.0','v0.19.0')
    change('src/app/main.c','static int smoke_response_control,smoke_response_preset,smoke_response_legacy,smoke_response_active;',
        'static int smoke_response_control,smoke_response_preset,smoke_response_legacy,smoke_response_active;\nstatic int smoke_color_control,smoke_color_preset,smoke_color_legacy,smoke_color_active;')
    change('src/app/main.c','params.response_shape=.613456789123456;',
        'params.response_shape=.613456789123456;params.event_color=.543456789123456;')
    change('src/app/main.c','params.response_shape=.843456789123456;slider_values();',
        'params.response_shape=.843456789123456;params.event_color=.783456789123456;slider_values();')
    change('src/app/main.c','before=saved;before.pressure_texture=before.structure_transfer=before.response_shape=0;',
        'WritePrivateProfileStringW(L"VSL",L"event_color",NULL,diagnostic_path(L"ui_character_precise.ini"));\n                        before=saved;before.pressure_texture=before.structure_transfer=before.response_shape=before.event_color=0;')
    change('src/app/main.c','before=saved;before.response_shape=0;',
        'WritePrivateProfileStringW(L"VSL",L"event_color",NULL,diagnostic_path(L"ui_response_legacy.ini"));\n                        before=saved;before.response_shape=before.event_color=0;')
    color_test='''                    {
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
'''
    change('src/app/main.c','                    params=saved;\n                    SendMessageW(sliders[7]',color_test+'                    params=saved;\n                    SendMessageW(sliders[7]')
    change('src/app/main.c','                smoke_response_active=audio.response_shape_mix>.4&&audio.response_pressure_events>100;',
        '                smoke_response_active=audio.response_shape_mix>.4&&audio.response_pressure_events>100;\n                smoke_color_active=audio.event_color_mix>.4&&audio.event_color_events>100&&audio.event_color_max_mod>.05;')
    marker='                    fprintf(f,"\\\"combustion_control\\\":%s,'
    insertion='                    fprintf(f,"\\\"event_color_control\\\":%s,\\\"event_color_preset_roundtrip\\\":%s,\\\"event_color_legacy_preset\\\":%s,\\\"event_color_active_on_device\\\":%s,",smoke_color_control?"true":"false",smoke_color_preset?"true":"false",smoke_color_legacy?"true":"false",smoke_color_active?"true":"false");\n'
    change('src/app/main.c',marker,insertion+marker)
    change('src/app/main.c','for(c=106;c<=108;++c)','for(c=106;c<=109;++c)')
    change('src/app/take_smoke.c','VslResponseShape expected_response=a->engine->response;int response_state=0,device_response=0;',
        'VslResponseShape expected_response=a->engine->response;int response_state=0,device_response=0;\n    VslEventColor expected_color=a->engine->color;int color_state=0,device_color=0;')
    change('src/app/take_smoke.c','        response_state=!memcmp(&expected_response,&e->response,sizeof expected_response);',
        '        response_state=!memcmp(&expected_response,&e->response,sizeof expected_response);\n        color_state=!memcmp(&expected_color,&e->color,sizeof expected_color);')
    change('src/app/take_smoke.c','        device_response=!memcmp(&expected_response,&a->engine->response,sizeof expected_response);',
        '        device_response=!memcmp(&expected_response,&a->engine->response,sizeof expected_response);\n        device_color=!memcmp(&expected_color,&a->engine->color,sizeof expected_color);')
    change('src/app/take_smoke.c','\\\"device_response_state_match\\\":%d,\\\"result\\\":",character_state,device_character,response_state,device_response);',
        '\\\"device_response_state_match\\\":%d,\\\"event_color_state_match\\\":%d,\\\"device_event_color_state_match\\\":%d,\\\"result\\\":",character_state,device_character,response_state,device_response,color_state,device_color);')
    change('tests/test_take.c','p.response_shape=.317234567891234;','p.response_shape=.317234567891234;p.event_color=.571234567891234;')
    change('tests/test_take.c','p.response_shape=.843456789123456;','p.response_shape=.843456789123456;p.event_color=.891234567891234;')
    change('tests/test_take.c','p.mechanical_model=0;p.response_shape=0;','p.mechanical_model=0;p.response_shape=0;p.event_color=0;')
    change('tests/test_take.c','"fields 35","fields 34"','"fields 36","fields 35"')
    change('tests/test_take.c','"VSLTAKE 3","VSLTAKE 2"','"VSLTAKE 4","VSLTAKE 3"')
    change('tests/test_take.c','    CHECK(!vsl_take_begin(&t,e),',
        '    CHECK(!memcmp(&e->color,&r->color,sizeof e->color),"complete main-pressure state reconstructed");\n    CHECK(!memcmp(&r->color,&m->color,sizeof r->color),"main-pressure state independent of layout");\n    CHECK(!vsl_take_begin(&t,e),')
    change('tests/test_take.c','    t.events[0].params.propagation=2;',
        '    t.events[0].params.event_color=1.1;CHECK(!vsl_take_validate(&t),"main-pressure range enforced");t.events[0].params.event_color=0;\n    t.events[0].params.propagation=2;')
    change('tools/v016_probe.c','(argc!=8&&argc!=9)','(argc<8||argc>10)')
    change('tools/v016_probe.c','[response_shape] (ASCII','[response_shape [event_color]] (ASCII')
    change('tools/v016_probe.c','    if(argc==9&&!number(argv[8],0,1,&p.response_shape))return 1;',
        '    if(argc>=9&&!number(argv[8],0,1,&p.response_shape))return 1;\n    if(argc==10&&!number(argv[9],0,1,&p.event_color))return 1;')
    change('build.ps1',"'build-v018'","'build-v019'")
    active='''                smoke_propagation_active=audio.propagation_mix>.999&&audio.propagation_clamped_paths==0;
                smoke_character_active=audio.character_pressure_mix>.4&&audio.character_structure_mix>.4&&audio.character_events>100;
                smoke_response_active=audio.response_shape_mix>.4&&audio.response_pressure_events>100;
                smoke_color_active=audio.event_color_mix>.4&&audio.event_color_events>100&&audio.event_color_max_mod>.05;
'''
    change('src/app/main.c',active,'')
    change('src/app/main.c','            if(smoke_tick==110) {\n                HWND details=',
        '            if(smoke_tick==110) {\n                /* Observe the known nondefault device state before UI tests\n                   intentionally change its switches and slider targets. */\n                EnterCriticalSection(&audio.lock);\n'+active+'                LeaveCriticalSection(&audio.lock);\n                HWND details=')
    # No write occurs before every unique marker and destination is checked.
    for name,text in files.items():(ROOT/name).write_text(text,encoding='utf-8')
    print('Native0.19 modules,field,UI and schema4 integrated;build and verification required.')


if __name__=='__main__':main()

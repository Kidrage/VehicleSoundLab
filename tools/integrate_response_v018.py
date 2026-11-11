"""One-time native integration from the immutable response-shape prototype."""
from pathlib import Path
import re
import json
from runtime_review import ROOT,sha


def change(name,old,new):
    path=ROOT/name;text=path.read_text(encoding='utf-8');assert text.count(old)==1,(name,old)
    path.write_text(text.replace(old,new),encoding='utf-8')


def main():
    assert '"0.17.0"' in (ROOT/'src/core/types.h').read_text()
    frozen=json.loads((ROOT/'baselines/v0.17.0/manifest.json').read_text(encoding='utf-8'))
    for item in frozen['files']:
        if item['path'].startswith(('src/','tests/')):assert sha(ROOT/item['path'])==item['sha256'],item['path']
    experiment=ROOT/'baselines/response_shape_v1/experiments/response_shape_v1'
    for source,target in [('kernel.h','src/core/response_kernel.h'),('kernel.c','src/core/response_kernel.c'),
        ('profile.h','src/profiles/response_shape.h'),('profile.c','src/profiles/response_shape.c'),('response.c','src/core/response_shape.c')]:
        path=ROOT/target;assert not path.exists()
        text=(experiment/source).read_text(encoding='utf-8')
        text=text.replace('"kernel.h"','"core/response_kernel.h"').replace('"profile.h"','"profiles/response_shape.h"').replace('"response.h"','"core/response_shape.h"')
        path.write_text(text,encoding='utf-8')
    text=(experiment/'response.h').read_text(encoding='utf-8')
    state=text[text.index('typedef struct {'):text.index('void vsl_response_init')]
    (ROOT/'src/core/response_types.h').write_text('#ifndef VSL_RESPONSE_TYPES_H\n#define VSL_RESPONSE_TYPES_H\n#include "response_kernel.h"\n#include <stdint.h>\n'+state+'#endif\n',encoding='utf-8')
    declarations=text[text.index('void vsl_response_init'):text.index('void vsl_response_character_tick')]
    (ROOT/'src/core/response_shape.h').write_text('#ifndef VSL_RESPONSE_SHAPE_H\n#define VSL_RESPONSE_SHAPE_H\n#include "engine.h"\n'+declarations+'#endif\n',encoding='utf-8')
    change('src/core/types.h','#define VSL_VERSION "0.17.0"','#define VSL_VERSION "0.18.0"')
    change('src/core/types.h','#include "character_types.h"','#include "character_types.h"\n#include "response_types.h"')
    change('src/core/types.h','double pressure_texture,structure_transfer;','double pressure_texture,structure_transfer,response_shape;')
    change('src/core/types.h','    VslCharacter character;','    VslCharacter character;\n    VslResponseShape response;')
    change('src/core/engine.c','UNIT(pressure_texture);UNIT(structure_transfer);','UNIT(pressure_texture);UNIT(structure_transfer);UNIT(response_shape);')
    change('src/core/engine.c','FOLLOW(pressure_texture);FOLLOW(structure_transfer);','FOLLOW(pressure_texture);FOLLOW(structure_transfer);FOLLOW(response_shape);')
    change('src/core/character.c','#include "character.h"','#include "character.h"\n#include "response_shape.h"')
    change('src/core/character.c','    vsl_character_pressure_init(&s->pressure,e->sample_rate);\n    vsl_character_structure_init',
        '    vsl_response_init(&e->response,e->sample_rate,0);\n    vsl_character_pressure_init(&s->pressure,e->sample_rate);\n    vsl_character_structure_init')
    change('src/core/character.c','        vsl_character_pressure_init(&s->pressure,e->sample_rate);',
        '        vsl_response_clear(&e->response);\n        vsl_character_pressure_init(&s->pressure,e->sample_rate);')
    change('src/core/character.c','    vsl_character_pressure_advance(&s->pressure);',
        '    e->response.amount=e->smooth.response_shape;vsl_response_begin(&e->response);\n    vsl_character_pressure_advance(&s->pressure);')
    change('src/core/character.c','vsl_character_pressure_strike(&s->pressure,engine->bank[c],pressure_gain,shape,elapsed);',
        'vsl_response_pressure_strike(&e->response,e,&s->pressure,engine->bank[c],pressure_gain,shape,elapsed);')
    change('src/core/character.c','vsl_character_structure_strike(&s->structure,structure_gain,shape,elapsed);',
        'vsl_response_structure_strike(&e->response,e,&s->structure,structure_gain,shape,elapsed);')
    path=ROOT/'src/core/character.c';text=path.read_text();assert text.endswith('    }\n}\n')
    path.write_text(text[:-2]+'    vsl_response_apply(&e->response,e,o);\n}\n',encoding='utf-8')
    change('src/core/profiles.c','p.pressure_texture=0;p.structure_transfer=0;',
        'p.response_shape=0; /* Optional shape control; missing presets stay off. */\n    p.pressure_texture=0;p.structure_transfer=0;')
    change('CMakeLists.txt','VERSION 0.17.0','VERSION 0.18.0')
    change('CMakeLists.txt','  src/core/character.c src/core/pressure_texture.c src/core/structure_texture.c src/profiles/character.c',
        '  src/core/character.c src/core/pressure_texture.c src/core/structure_texture.c src/profiles/character.c\n  src/core/response_kernel.c src/core/response_shape.c src/profiles/response_shape.c')
    change('CMakeLists.txt','enable_testing()',
        'enable_testing()\nadd_executable(vsl_response_tests tests/test_response_shape.c)\ntarget_link_libraries(vsl_response_tests PRIVATE vsl_core)\nadd_test(NAME live_response_shape COMMAND vsl_response_tests)')
    change('src/session/parameters.h',' D(pressure_texture) D(structure_transfer)',' D(pressure_texture) D(structure_transfer) D(response_shape)')
    change('src/io/take_file.c','VSLTAKE 2\\n','VSLTAKE 3\\n')
    change('src/io/take_file.c','!word(f,"VSLTAKE")||!word(f,"2")','!word(f,"VSLTAKE")||!word(f,"3")')
    change('src/io/scene_metadata.c','FIELD(pressure_texture);FIELD(structure_transfer);','FIELD(pressure_texture);FIELD(structure_transfer);FIELD(response_shape);')
    change('src/io/drive_trace.c','    fputc(\'\\n\',f);\n}\nvoid vsl_trace_frame',
        '    fputs(",response_shape_target,response_shape_mix,response_pressure_events,response_structure_events",f);\n    fputc(\'\\n\',f);\n}\nvoid vsl_trace_frame')
    path=ROOT/'src/io/drive_trace.c';text=path.read_text();i=text.rindex("    fputc('\\n',f);")
    text=text[:i]+'    fprintf(f,",%.12g,%.12g,%llu,%llu",e->target.response_shape,e->response.amount,\n        (unsigned long long)e->response.pressure_events,(unsigned long long)e->response.structure_events);\n'+text[i:];path.write_text(text,encoding='utf-8')
    change('src/app/preset.c','D(pressure_texture),D(structure_transfer)}','D(pressure_texture),D(structure_transfer),D(response_shape)}')
    change('src/app/tuning.c','static HWND character_sliders[2],character_labels[2];','static HWND character_sliders[3],character_labels[3];')
    change('src/app/tuning.c','SetWindowTextW(character_labels[1],text); }',
        'SetWindowTextW(character_labels[1],text);\n      swprintf(text,100,L"Response shape (test)    %.0f%%",params->response_shape*100);SetWindowTextW(character_labels[2],text); }')
    change('src/app/tuning.c','for(i=0;i<2;++i) {\n            int x=20+i*320;',
        'for(i=0;i<3;++i) {\n            int x=20+(i%2)*320,y=488+(i/2)*66;')
    change('src/app/tuning.c','x,488,310,22','x,y,310,22')
    change('src/app/tuning.c','x-4,512,300,30','x-4,y+24,300,30')
    change('src/app/tuning.c','        label_values();SendMessageW(owner,VSL_TUNING_CHANGED,0,0);return 0;',
        '        if((HWND)l==character_sliders[2])params->response_shape=SendMessageW(character_sliders[2],TBM_GETPOS,0,0)/1000.;\n        label_values();SendMessageW(owner,VSL_TUNING_CHANGED,0,0);return 0;')
    change('src/app/tuning.c','    Button_SetCheck(fuel_switch,params->fuel_cut);',
        '    SendMessageW(character_sliders[2],TBM_SETPOS,TRUE,(LPARAM)(params->response_shape*1000));\n    Button_SetCheck(fuel_switch,params->fuel_cut);')
    change('src/app/tuning.c','RECT size={0,0,660,552}','RECT size={0,0,660,618}')
    change('src/app/audio_device.h','    unsigned character_events;','    unsigned character_events;\n    double response_shape_mix;\n    uint64_t response_pressure_events;')
    change('src/app/audio_device.c','                a->character_events=vsl_character_events(&a->engine->character);',
        '                a->character_events=vsl_character_events(&a->engine->character);\n                a->response_shape_mix=a->engine->response.amount;\n                a->response_pressure_events=a->engine->response.pressure_events;')
    for name in ['src/app/main.c','src/app/take_smoke.c']:
        path=ROOT/name;path.write_text(path.read_text(encoding='utf-8').replace('v0.17.0','v0.18.0'),encoding='utf-8')
    change('tests/test_take.c','p.structure_transfer=.617234567891234;','p.structure_transfer=.617234567891234;p.response_shape=.317234567891234;')
    change('tests/test_take.c','p.structure_transfer=.891234567891234;','p.structure_transfer=.891234567891234;p.response_shape=.843456789123456;')
    change('tests/test_take.c','p.throttle=0;p.propagation=0;p.mechanical_model=0;','p.throttle=0;p.propagation=0;p.mechanical_model=0;p.response_shape=0;')
    change('tests/test_take.c','"fields 34","fields 35"','"fields 35","fields 34"')
    change('tests/test_take.c','"VSLTAKE 2","VSLTAKE 1"','"VSLTAKE 3","VSLTAKE 2"')
    change('tests/test_take.c','    CHECK(!vsl_take_begin(&t,e),',
        '    CHECK(!memcmp(&e->response,&r->response,sizeof e->response),"complete response shape state reconstructed");\n    CHECK(!memcmp(&r->response,&m->response,sizeof r->response),"response state independent of layout");\n    CHECK(!vsl_take_begin(&t,e),')
    change('tests/test_take.c','    t.events[0].params.propagation=2;',
        '    t.events[0].params.response_shape=1.1;CHECK(!vsl_take_validate(&t),"response shape range enforced");t.events[0].params.response_shape=0;\n    t.events[0].params.propagation=2;')
    # Fresh diagnostic capture can now accept an explicit shape parameter.
    change('tools/v016_probe.c','if(argc!=8||snprintf','if((argc!=8&&argc!=9)||snprintf')
    change('tools/v016_probe.c','pressure structure (ASCII','pressure structure [response_shape] (ASCII')
    change('tools/v016_probe.c','    e=malloc(sizeof *e);',
        '    if(argc==9&&!number(argv[8],0,1,&p.response_shape))return 1;\n    e=malloc(sizeof *e);')
    print('Native response modules,control field,UI and schema3 integrated; build and verification still required.')


if __name__=='__main__':main()

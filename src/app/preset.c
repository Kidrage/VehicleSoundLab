#define _CRT_SECURE_NO_WARNINGS
#include "preset.h"
#include "core/engine.h"
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
typedef struct { const wchar_t *name;size_t offset;int integer; } Field;
#define WIDE2(s) L##s
#define WIDE(s) WIDE2(s)
#define D(f) {WIDE(#f),offsetof(VslParams,f),0}
#define I(f) {WIDE(#f),offsetof(VslParams,f),1}
static const Field fields[]={I(profile),I(pure_osc),D(rpm),D(load),D(master),D(dna),D(pad),D(noise),D(brightness),D(space),
    I(drive_mode),I(ignition),I(start_id),I(gear),I(auto_gear),I(backfire),D(throttle),D(brake),D(width),D(perspective),D(detail),D(intake),D(mechanical),
    D(idle_body),D(irregularity),D(release_time),D(event_level),I(fuel_cut),D(pumping),I(mechanical_model),I(combustion_variation),I(propagation),D(pressure_texture),D(structure_transfer),D(response_shape),D(event_color),I(firing_source),D(pulse_amount)};
#undef D
#undef I
void vsl_preset_save(const wchar_t *file,const VslParams *p,const wchar_t *dna,const wchar_t *ir) {
    unsigned i;
    WritePrivateProfileStringW(L"VSL",L"version",VSL_VERSION_W,file);
    WritePrivateProfileStringW(L"VSL",L"seed",L"48271",file);
    for(i=0;i<sizeof fields/sizeof fields[0];++i) {
        wchar_t value[64];const char *v=(const char*)p+fields[i].offset;
        double number=fields[i].integer?*(const int*)v:*(const double*)v;
        swprintf(value,64,L"%.17g",number);WritePrivateProfileStringW(L"VSL",fields[i].name,value,file);
    }
    WritePrivateProfileStringW(L"VSL",L"dna_file",dna,file);WritePrivateProfileStringW(L"VSL",L"ir_file",ir,file);
}
int vsl_preset_load(const wchar_t *file,VslParams *p,wchar_t *dna,wchar_t *ir) {
    unsigned i;wchar_t version[32];
    GetPrivateProfileStringW(L"VSL",L"version",L"",version,32,file);
    if(!version[0])return 0;
    *p=vsl_default_params(0);
    /* Presets predating 0.8 have no model selector: retain their old voice. */
    p->mechanical_model=0;
    p->combustion_variation=0;
    p->propagation=0; /* Missing in historical presets: preserve their renderer. */
    for(i=0;i<sizeof fields/sizeof fields[0];++i) {
        wchar_t value[64];char *v=(char*)p+fields[i].offset;
        GetPrivateProfileStringW(L"VSL",fields[i].name,L"",value,64,file);
        if(value[0]) { if(fields[i].integer)*(int*)v=_wtoi(value);else *(double*)v=_wtof(value); }
    }
    GetPrivateProfileStringW(L"VSL",L"dna_file",L"",dna,MAX_PATH,file);
    GetPrivateProfileStringW(L"VSL",L"ir_file",L"",ir,MAX_PATH,file);return 1;
}

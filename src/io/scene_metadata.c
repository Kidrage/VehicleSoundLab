#include "scene_metadata.h"
#include "file.h"
#include "core/engine.h"
#include "spatial/scene.h"
#include "profiles/propagation.h"
#include <stdio.h>
#include <stdlib.h>
static void json_string(FILE *f,const char *value) {
    const unsigned char *s=(const unsigned char*)(value?value:"");fputc('"',f);
    for(;*s;++s) {
        if(*s=='"'||*s=='\\') { fputc('\\',f);fputc(*s,f); }
        else if(*s<32)fprintf(f,"\\u%04x",*s);
        else fputc(*s,f);
    }
    fputc('"',f);
}
int vsl_write_scene_metadata(const char *path,const VslParams *params,int channels,const char *prefix) {
    VslEngine *e;VslParams p;FILE *f;int i,ok;
    if(channels!=2&&channels!=12)return 0;
    e=(VslEngine*)malloc(sizeof *e);if(!e)return 0;
    vsl_init(e,48000,48271);vsl_set_params(e,params);p=e->target;free(e);
    f=vsl_fopen(path,"w");if(!f)return 0;
    fprintf(f,"{\n\"schema\":\"vsl.scene/1\",\"dsp_version\":\"%s\",\"sample_rate\":48000,\"seed\":48271,\n",VSL_VERSION);
    fprintf(f,"\"coordinates\":\"metres; +x vehicle front, +y left, +z up\",\n");
    for(i=0;i<2;++i) { double x,y,z;vsl_listener_position(i,&x,&y,&z);fprintf(f,"\"listener_%s\":[%.6g,%.6g,%.6g],\n",i?"cabin":"exterior",x,y,z); }
    fprintf(f,"\"format\":\"WAVE speaker bed; pre-master mono float32 source stems separately; not Atmos object metadata\",\n");
    fprintf(f,"\"heights\":\"synthetic early reflections only; no duplicated direct engine\",\n\"lfe\":\"0.22 linear low feed, one-pole 120 Hz; uncalibrated bass management\",\n");
    {
        const VslPropagationProfile *a=vsl_propagation_profile();
        fprintf(f,"\"direct_propagation\":{\"enabled\":%s,\"speed_mps\":%.12g,\"ear_spacing_m\":%.12g,\"reference_distance_m\":%.12g,\"minimum_distance_m\":%.12g,\"follow_seconds\":%.12g,\"shadow_hz\":%.12g,\"shadow_fraction\":%.12g,\"policy\":\"stereo per-ear paths; speaker-bed centre path without ear/head transfer; existing early reflections unchanged; engineering model, not measured HRTF or room\"},\n",
            p.propagation?"true":"false",a->speed_mps,a->ear_spacing_m,a->reference_distance_m,a->minimum_distance_m,a->follow_seconds,a->shadow_hz,a->shadow_fraction);
    }
    fprintf(f,"\"propagation_filter\":{\"taps\":%d,\"phases\":%d,\"algorithmic_latency_samples\":%d,\"type\":\"table-interpolated Blackman sinc; common FIR latency is separate from acoustic distance\"},\n",VSL_PATH_TAPS,VSL_PATH_PHASES,VSL_PATH_LATENCY);
    fprintf(f,"\"channels\":[");for(i=0;i<channels;++i) { if(i)fputc(',',f);json_string(f,vsl_channel_name(channels,i)); }fprintf(f,"],\n\"parameters\":{");
#define FIELD(name) fprintf(f,"\"" #name "\":%.12g,",(double)p.name)
    FIELD(profile);FIELD(pure_osc);FIELD(drive_mode);FIELD(rpm);FIELD(load);FIELD(throttle);FIELD(brake);
    FIELD(ignition);FIELD(start_id);FIELD(gear);FIELD(auto_gear);FIELD(backfire);
    FIELD(width);FIELD(perspective);FIELD(master);FIELD(dna);FIELD(pad);FIELD(noise);FIELD(brightness);FIELD(space);
    FIELD(detail);FIELD(intake);FIELD(mechanical);FIELD(idle_body);FIELD(irregularity);FIELD(release_time);
    FIELD(fuel_cut);FIELD(pumping);FIELD(mechanical_model);FIELD(combustion_variation);
    FIELD(propagation);FIELD(pressure_texture);FIELD(structure_transfer);FIELD(response_shape);FIELD(event_color);FIELD(firing_source);FIELD(pulse_amount);
#undef FIELD
    fprintf(f,"\"event_level\":%.12g},\n\"objects\":[\n",p.event_level);
    for(i=0;i<VSL_OBJECTS;++i) {
        const VslObjectInfo *o=vsl_object_info(i);char name[4096];
        fprintf(f,"{\"name\":");json_string(f,o->name);fprintf(f,",\"position\":[%.6g,%.6g,%.6g],\"channels\":1,\"level\":\"pre-master, pre-spatial, no endpoint fade\"",o->x,o->y,o->z);
        if(prefix&&*prefix) { snprintf(name,sizeof name,"%s_%s.wav",prefix,o->name);fprintf(f,",\"file\":");json_string(f,name); }
        fprintf(f,"}%s\n",i==VSL_OBJECTS-1?"":",");
    }
    fprintf(f,"]\n}\n");ok=!ferror(f);if(fclose(f))ok=0;return ok;
}

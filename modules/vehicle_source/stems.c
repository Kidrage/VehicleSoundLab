#include "internal.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>
static const VsStemInfo info[VS_STEMS]={
    {"dna","Sound DNA","observed_stereo",2,1,1},
    {"low","Low body","observed_stereo",2,1,1},
    {"detail","Detail","observed_stereo",2,1,1},
    {"intake","Intake","procedural_intake",1,.7071067811865475,.7071067811865475},
    {"mechanical","Mechanical","procedural_mechanical",1,.7071067811865475,.7071067811865475},
    {"exhaust_air","Exhaust air","procedural_stereo",2,1,1},
    {"road","Road","procedural_road",1,.7071067811865475,.7071067811865475},
    {"wind","Wind","procedural_wind",1,.7071067811865475,.7071067811865475},
    {"startup","Startup texture","observed_stereo",2,1,1},
    {"catch","Catch support","observed_stereo",2,1,1},
    {"added","Additional source","observed_stereo",2,1,1},
    {"legacy_event","Legacy event and starter","legacy_procedural_event",1,1,1},
    {"event_0","Event voice 1","event_slot_with_instance_notices",1,.7071067811865475,.7071067811865475},
    {"event_1","Event voice 2","event_slot_with_instance_notices",1,.7071067811865475,.7071067811865475},
    {"event_2","Event voice 3","event_slot_with_instance_notices",1,.7071067811865475,.7071067811865475},
    {"event_3","Event voice 4","event_slot_with_instance_notices",1,.7071067811865475,.7071067811865475}
};
const VsStemInfo *vs_stem_info(unsigned k){return k<VS_STEMS?info+k:NULL;}
int vs_output_valid(const VsOutput *out,unsigned frames) {
    const float *p[VS_STEMS+1];size_t bytes[VS_STEMS+1];unsigned i,j;
    if(!out||frames>VS_BLOCK_MAX)return 0;
    p[0]=out->monitor;bytes[0]=(size_t)frames*2*sizeof(float);
    for(i=0;i<VS_STEMS;++i){p[i+1]=out->stem[i];bytes[i+1]=(size_t)frames*info[i].channels*sizeof(float);}
    for(i=0;i<=VS_STEMS;++i)if(p[i]) {
        uintptr_t begin=(uintptr_t)p[i];if(begin>UINTPTR_MAX-bytes[i])return 0;
        for(j=0;j<i;++j)if(p[j]) {
            uintptr_t other=(uintptr_t)p[j];
            if(begin<other+bytes[j]&&other<begin+bytes[i])return 0;
        }
    }
    return 1;
}
static void write_stem(VsOutput *out,unsigned k,unsigned n,unsigned channel,double x) {
    if(out->stem[k])out->stem[k][n*info[k].channels+channel]=(float)x;
}
void vs_stems_write(VsEngine *s,VsOutput *out,unsigned frames,double gain) {
    unsigned n,c;
    if(out->monitor)memcpy(out->monitor,s->monitor,(size_t)frames*2*sizeof(float));
    for(n=0;n<frames;++n) {
        gain+=s->generator.follow*(s->adopted.mix.gain-gain);
        for(c=0;c<2;++c) {
            unsigned p=2*n+c;
            write_stem(out,VS_DNA,n,c,gain*s->dna[p]);
            write_stem(out,VS_LOW,n,c,gain*((double)s->body[p]+s->low[p]));
            write_stem(out,VS_DETAIL,n,c,gain*((double)s->residual[p]+s->resonant[p]));
            write_stem(out,VS_EXHAUST_AIR,n,c,gain*s->aux[n*VSL_OBJECTS+(c?VSL_AIR_R:VSL_AIR_L)]);
            write_stem(out,VS_STARTUP,n,c,gain*s->startup[p]);
            write_stem(out,VS_CATCH,n,c,gain*s->catching[p]);
            write_stem(out,VS_ADDED,n,c,gain*s->added[p]);
        }
        write_stem(out,VS_INTAKE,n,0,gain*s->aux[n*VSL_OBJECTS+VSL_INTAKE]);
        write_stem(out,VS_MECHANICAL,n,0,gain*s->aux[n*VSL_OBJECTS+VSL_MECHANICAL]);
        write_stem(out,VS_ROAD,n,0,gain*s->aux[n*VSL_OBJECTS+VSL_ROAD]);
        write_stem(out,VS_WIND,n,0,gain*s->aux[n*VSL_OBJECTS+VSL_WIND]);
        write_stem(out,VS_LEGACY_EVENT,n,0,s->events[n]*gain);
        double events=0;
        for(c=0;c<ES_VOICES;++c) {
            double x=s->event_voices[c][n]*gain;write_stem(out,VS_EVENT_0+c,n,0,x);
            events+=x*.7071067811865475;
        }
        if(out->monitor&&events!=0) {
            out->monitor[2*n]+=(float)events;out->monitor[2*n+1]+=(float)events;
        }
    }
}

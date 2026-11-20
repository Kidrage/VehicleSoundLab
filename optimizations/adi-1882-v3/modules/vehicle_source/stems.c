#include "dsp/perf.h"
#include "internal.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "dsp_support/storage.h"
static const VsStemInfo info[VS_STEMS]={
    {"dna","Sound DNA","observed_stereo",2,1,1},
    {"low","Low body","observed_stereo",2,1,1},
    {"detail","Detail","observed_stereo",2,1,1},
    {"intake","Intake","procedural_intake",1,.7071067811865475f,.7071067811865475f},
    {"mechanical","Mechanical","procedural_mechanical",1,.7071067811865475f,.7071067811865475f},
    {"exhaust_air","Exhaust air","procedural_stereo",2,1,1},
    {"road","Road","procedural_road",1,.7071067811865475f,.7071067811865475f},
    {"wind","Wind","procedural_wind",1,.7071067811865475f,.7071067811865475f},
    {"startup","Startup texture","observed_stereo",2,1,1},
    {"catch","Catch support","observed_stereo",2,1,1},
    {"added","Additional source","observed_stereo",2,1,1},
    {"legacy_event","Legacy event and starter","legacy_procedural_event",1,1,1},
    {"event_0","Event voice 1","event_slot_with_instance_notices",1,.7071067811865475f,.7071067811865475f},
    {"event_1","Event voice 2","event_slot_with_instance_notices",1,.7071067811865475f,.7071067811865475f},
    {"event_2","Event voice 3","event_slot_with_instance_notices",1,.7071067811865475f,.7071067811865475f},
    {"event_3","Event voice 4","event_slot_with_instance_notices",1,.7071067811865475f,.7071067811865475f}
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
#if defined(VSL_ADSP_21569) && defined(VSL_DSP_APPROX)
#pragma always_inline
#endif
static inline void write_stem(VsOutput *out,unsigned k,unsigned n,unsigned channel,float x) {
    if(out->stem[k])out->stem[k][n*info[k].channels+channel]=(float)x;
}
#ifdef VSL_DSP_STATIC
VSL_SECTION(VSL_L1_STATE)
static float stem_gains[VS_BLOCK_MAX];
/* Write one contiguous stem at a time. The gain recurrence, FP32 expression
   order and event summation are identical to the sample-major implementation.
   This avoids revisiting 23 distant DDR streams for every audio sample. */
static void stem_copy(float *restrict dst,const float *restrict src,
                      unsigned frames,unsigned channels){
    unsigned n,c;if(!dst)return;
    for(n=0;n<frames;++n)for(c=0;c<channels;++c)
        dst[n*channels+c]=stem_gains[n]*src[n*channels+c];
}
static void stem_sum(float *restrict dst,const float *restrict a,
                     const float *restrict b,unsigned frames){
    unsigned n;if(!dst)return;
    for(n=0;n<2*frames;++n)dst[n]=stem_gains[n/2]*(a[n]+b[n]);
}
static void stem_aux(float *restrict dst,const float *restrict src,
                     unsigned frames,unsigned left,unsigned right,unsigned channels){
    unsigned n;if(!dst)return;
    for(n=0;n<frames;++n){
        dst[n*channels]=stem_gains[n]*src[n*VSL_OBJECTS+left];
        if(channels==2)dst[n*channels+1]=stem_gains[n]*src[n*VSL_OBJECTS+right];
    }
}
static void stems_block(VsEngine *s,VsOutput *out,unsigned frames,float gain){
    unsigned n,c;
    if(out->monitor)memcpy(out->monitor,s->monitor,(size_t)frames*2*sizeof(float));
    for(n=0;n<frames;++n){
        gain+=s->generator.follow*(s->adopted.mix.gain-gain);stem_gains[n]=gain;
    }
    stem_copy(out->stem[VS_DNA],s->dna,frames,2);
    stem_sum(out->stem[VS_LOW],s->body,s->low,frames);
    stem_sum(out->stem[VS_DETAIL],s->residual,s->resonant,frames);
    stem_aux(out->stem[VS_EXHAUST_AIR],s->aux,frames,VSL_AIR_L,VSL_AIR_R,2);
    stem_copy(out->stem[VS_STARTUP],s->startup,frames,2);
    stem_copy(out->stem[VS_CATCH],s->catching,frames,2);
    stem_copy(out->stem[VS_ADDED],s->added,frames,2);
    stem_aux(out->stem[VS_INTAKE],s->aux,frames,VSL_INTAKE,0,1);
    stem_aux(out->stem[VS_MECHANICAL],s->aux,frames,VSL_MECHANICAL,0,1);
    stem_aux(out->stem[VS_ROAD],s->aux,frames,VSL_ROAD,0,1);
    stem_aux(out->stem[VS_WIND],s->aux,frames,VSL_WIND,0,1);
    stem_copy(out->stem[VS_LEGACY_EVENT],s->events,frames,1);
    for(c=0;c<ES_VOICES;++c)
        stem_copy(out->stem[VS_EVENT_0+c],s->event_voices[c],frames,1);
    if(out->monitor)for(n=0;n<frames;++n){
        float events=0;
        for(c=0;c<ES_VOICES;++c){
            float x=s->event_voices[c][n]*stem_gains[n];events+=x*.7071067811865475f;
        }
        if(events!=0){out->monitor[2*n]+=events;out->monitor[2*n+1]+=events;}
    }
}
#endif
void vs_stems_write(VsEngine *s,VsOutput *out,unsigned frames,float gain);
void vs_stems_write_impl(VsEngine *s,VsOutput *out,unsigned frames,float gain){
#ifdef VSL_DSP_STATIC
    stems_block(s,out,frames,gain);
#else
    unsigned n,c;
    if(out->monitor)memcpy(out->monitor,s->monitor,(size_t)frames*2*sizeof(float));
    for(n=0;n<frames;++n) {
        gain+=s->generator.follow*(s->adopted.mix.gain-gain);
        for(c=0;c<2;++c) {
            unsigned p=2*n+c;
            write_stem(out,VS_DNA,n,c,gain*s->dna[p]);
            write_stem(out,VS_LOW,n,c,gain*((float)s->body[p]+s->low[p]));
            write_stem(out,VS_DETAIL,n,c,gain*((float)s->residual[p]+s->resonant[p]));
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
        float events=0;
        for(c=0;c<ES_VOICES;++c) {
            float x=s->event_voices[c][n]*gain;write_stem(out,VS_EVENT_0+c,n,0,x);
            events+=x*.7071067811865475f;
        }
        if(out->monitor&&events!=0) {
            out->monitor[2*n]+=(float)events;out->monitor[2*n+1]+=(float)events;
        }
    }
#endif
}
void vs_stems_write(VsEngine *s,VsOutput *out,unsigned frames,float gain){vsl_perf_enter(11);vs_stems_write_impl(s,out,frames,gain);vsl_perf_leave();}


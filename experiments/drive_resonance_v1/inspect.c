#define _CRT_SECURE_NO_WARNINGS
#include "inspect.h"
#include "atlas_take/player.h"
#include "drive/drive.h"
#include "drive/lifecycle.h"
#include "io/file.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    uint64_t frames,supported,low_supported;
    double rpm_min,rpm_max,support_sum,dna_power,detail_power,low_power;
} DrpState;
static void observe(DrpState *s,const AdTelemetry *t,const float *dna,const float *detail,const float *low) {
    if(!s->frames)s->rpm_min=s->rpm_max=t->rpm;
    ++s->frames;if(t->resonant_support>0)++s->supported;
    if(t->coherent_low_support>0)++s->low_supported;
    s->rpm_min=fmin(s->rpm_min,t->rpm);s->rpm_max=fmax(s->rpm_max,t->rpm);
    s->support_sum+=t->resonant_support;
    for(unsigned c=0;c<2;++c){s->dna_power+=(double)dna[c]*dna[c];s->detail_power+=(double)detail[c]*detail[c];s->low_power+=(double)low[c]*low[c];}
}
static void state_json(FILE *f,const char *name,const DrpState *s,int comma) {
    fprintf(f,"%s\"%s\":{\"frames\":%llu,\"detail_supported_frames\":%llu,\"rpm_min\":%.17g,\"rpm_max\":%.17g,"
        "\"mean_support\":%.17g,\"dna_rms\":%.17g,\"detail_rms\":%.17g,\"low_rms\":%.17g,\"low_supported_frames\":%llu}",comma?",":"",name,
        (unsigned long long)s->frames,(unsigned long long)s->supported,s->rpm_min,s->rpm_max,
        s->frames?s->support_sum/s->frames:0,s->frames?sqrt(s->dna_power/(2*s->frames)):0,
        s->frames?sqrt(s->detail_power/(2*s->frames)):0,s->frames?sqrt(s->low_power/(2*s->frames)):0,
        (unsigned long long)s->low_supported);
}
int drp_inspect(const AtTake *take,const char *directory) {
    AtPlayer *p=calloc(1,sizeof *p);VslEngine *engine=calloc(1,sizeof *engine);
    DrpState operating[VSL_OPERATING_COUNT]={{0}},lifecycle[VSL_STOPPING+1]={{0}};
    float out[1024];AdTelemetry telemetry[512];VslWavWriter wav[5]={{0}};
    const char *names[]={"inspected.wav","dna_stem.wav","detail_stem.wav","coherent_low_stem.wav","coherent_low_raw.wav"};
    char path[4096];FILE *csv=NULL,*report=NULL;int ok=0;unsigned shifts=0,overruns=0;
    if(!p||!engine||!at_player_init(p,engine,take,2))goto done;
    for(unsigned i=0;i<5;++i){snprintf(path,sizeof path,"%s/%s",directory,names[i]);if(!vsl_wav_begin_float(wav+i,path,48000,2))goto done;}
    snprintf(path,sizeof path,"%s/pedal_trace.csv",directory);csv=vsl_fopen(path,"wb");if(!csv)goto done;
    fputs("frame,seconds,rpm,root_hz,speed_kph,load,gear,lifecycle,operating,shifts,overruns,lower,upper,blend,coverage,resonant_support,resonant_gain,dna_envelope,coherent_low_support,coherent_low_gain,coherent_low_envelope\n",csv);
    while(!at_player_complete(p)) {
        uint64_t at=p->render.frame,left=take->frames-at;unsigned n=left<512?(unsigned)left:512,index=p->next;
        /* Prevent internal event/transport splits so the three stem buffers all
           describe this entire call, rather than only its last sub-block. */
        while(index<take->count&&take->events[index].frame<=at)++index;
        if(index<take->count&&take->events[index].frame-at<n)n=(unsigned)(take->events[index].frame-at);
        if(take->stop_frame>at&&take->stop_frame-at<n)n=(unsigned)(take->stop_frame-at);
        if(!n||at_player_process(p,out,n,telemetry)!=n)goto done;
        if(!vsl_wav_write(wav,out,n)||!vsl_wav_write(wav+1,p->dna,n)||!vsl_wav_write(wav+2,p->resonant,n))goto done;
        if(!vsl_wav_write(wav+3,p->coherent_low,n)||!vsl_wav_write(wav+4,p->coherent_low_raw,n))goto done;
        for(unsigned j=0;j<n;++j) {
            const AdTelemetry *t=telemetry+j;
            if(t->lifecycle<0||t->lifecycle>VSL_STOPPING||t->operating<0||t->operating>=VSL_OPERATING_COUNT||
               !isfinite(t->rpm)||!isfinite(t->resonant_support))goto done;
            observe(lifecycle+t->lifecycle,t,p->dna+2*j,p->resonant+2*j,p->coherent_low+2*j);
            if(t->lifecycle==VSL_RUNNING)observe(operating+t->operating,t,p->dna+2*j,p->resonant+2*j,p->coherent_low+2*j);
            shifts=t->shifts;overruns=t->overruns;
            if(t->frame%240==0)fprintf(csv,"%llu,%.6f,%.17g,%.17g,%.17g,%.17g,%d,%d,%d,%u,%u,%u,%u,%.17g,%d,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g\n",
                (unsigned long long)t->frame,t->frame/48000.,t->rpm,t->root_hz,t->speed,t->load,t->gear,t->lifecycle,t->operating,
                t->shifts,t->overruns,t->lower,t->upper,t->blend,t->coverage,t->resonant_support,t->resonant_gain,t->envelope,
                t->coherent_low_support,t->coherent_low_gain,t->coherent_low_envelope);
        }
    }
    if(!at_player_verified(p)||ferror(csv))goto done;
    snprintf(path,sizeof path,"%s/state_inspection.json",directory);report=vsl_fopen(path,"wb");if(!report)goto done;
    fprintf(report,"{\"result\":\"pass\",\"frames\":%llu,\"source_hash\":\"%016llx\",\"output_hash\":\"%016llx\","
        "\"shifts\":%u,\"overruns\":%u,\"lifecycle\":{",(unsigned long long)take->frames,
        (unsigned long long)p->source_hash,(unsigned long long)p->audio_hash,shifts,overruns);
    for(unsigned i=0;i<=VSL_STOPPING;++i)state_json(report,vsl_lifecycle_name((VslLifecycle)i),lifecycle+i,i!=0);
    fputs("},\"running_operating\":{",report);
    for(unsigned i=0;i<VSL_OPERATING_COUNT;++i)state_json(report,vsl_operating_name((VslOperating)i),operating+i,i!=0);
    fputs("},\"limits\":\"Synthetic pedal controls and engineering RPM mapping, not real vehicle measurements or timbre acceptance. Stems precede host master/fades.\"}\n",report);
    ok=!ferror(report);
done:
    for(unsigned i=0;i<5;++i)if(wav[i].file&&!vsl_wav_end(wav+i))ok=0;
    if(csv&&fclose(csv))ok=0;if(report&&fclose(report))ok=0;free(engine);free(p);return ok;
}

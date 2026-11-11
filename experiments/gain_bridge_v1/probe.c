#define _CRT_SECURE_NO_WARNINGS
#include "bridge.h"
#include "io/take_file.h"
#include "io/wav.h"
#include "io/file.h"
#include "io/drive_trace.h"
#include "io/scene_metadata.h"
#include "spatial/scene.h"
#include <stdlib.h>
#include <stdio.h>
#include <inttypes.h>
#include <math.h>
#include <string.h>
static int carrier(const char *prefix) {
    VslGainBridge b;VslVoicing v={0};VslWavWriter gain={0},audio={0};
    unsigned frame,j;float pairs[VSL_BRIDGE_GAINS*2],x[2],g[2];int ok=0;char path[4096];
    if(strlen(prefix)>3800||!vsl_gain_bridge_init(&b,1))return 2;
    snprintf(path,sizeof path,"%s_gain.wav",prefix);if(!vsl_wav_begin_float(&gain,path,48000,2))goto done;
    snprintf(path,sizeof path,"%s_carrier.wav",prefix);if(!vsl_wav_begin_float(&audio,path,48000,2))goto done;
    ok=1;
    for(frame=0;frame<6*48000;++frame) {
        if(frame%240==0) { v.dna_gain=.5+.25*cos(2*VSL_PI*7*frame/48000.);vsl_gain_bridge_control(&b,&v,240); }
        vsl_gain_bridge_audio(&b,&v,pairs);
        for(j=0;j<2;++j) { g[j]=pairs[j];x[j]=(float)(pairs[j]*cos(2*VSL_PI*2048*frame/48000.)); }
        if(frame>=2*48000&&(!vsl_wav_write(&gain,g,1)||!vsl_wav_write(&audio,x,1))) { ok=0;break; }
    }
done:
    if(gain.file)ok=vsl_wav_end(&gain)&&ok;if(audio.file)ok=vsl_wav_end(&audio)&&ok;
    printf("gain bridge carrier control: 48k, 200Hz control, 7Hz modulation, 2048Hz carrier, 2s warmup+4s export | %s\n",ok?"pass":"FAIL");return ok?0:2;
}
int main(int argc,char **argv) {
    VslTake take={0};VslTakePlayer player;VslEngine *e=NULL;VslGainBridge bridge;
    VslWavWriter mix={0},stems[VSL_OBJECTS]={0},gains[VSL_BRIDGE_GAINS]={0};
    FILE *trace=NULL,*meta=NULL;float output[257*12],sources[257*VSL_OBJECTS];
    float pairs[257*VSL_BRIDGE_GAINS*2],mono[257],pair[257*2];
    char path[4096],*end;int mode,channels,c,ok=0;unsigned n,i;
    if(argc==3&&!strcmp(argv[1],"carrier"))return carrier(argv[2]);
    if(argc!=5||strlen(argv[2])>3800)return 1;
    mode=(int)strtol(argv[3],&end,10);if(end==argv[3]||*end||mode<0||mode>1)return 1;
    channels=(int)strtol(argv[4],&end,10);if(end==argv[4]||*end||(channels!=2&&channels!=12))return 1;
    e=malloc(sizeof *e);if(!e||!vsl_take_load(argv[1],&take)||!vsl_take_player_init(&player,e,&take)||!vsl_gain_bridge_init(&bridge,mode))goto done;
    snprintf(path,sizeof path,"%s.wav",argv[2]);if(!vsl_wav_begin_float(&mix,path,take.sample_rate,channels))goto done;
    for(c=0;c<VSL_OBJECTS;++c) {
        snprintf(path,sizeof path,"%s_source_%s.wav",argv[2],vsl_object_info(c)->name);
        if(!vsl_wav_begin_float(&stems[c],path,take.sample_rate,1))goto done;
    }
    for(c=0;c<VSL_BRIDGE_GAINS;++c) {
        snprintf(path,sizeof path,"%s_gain_%s.wav",argv[2],vsl_gain_bridge_name(c));
        if(!vsl_wav_begin_float(&gains[c],path,take.sample_rate,2))goto done;
    }
    snprintf(path,sizeof path,"%s.csv",argv[2]);trace=vsl_fopen(path,"w");if(!trace)goto done;vsl_trace_header(trace);
    ok=1;
    while((n=vsl_gain_bridge_take(&player,e,&bridge,output,257,channels,sources,pairs))!=0) {
        if(!vsl_wav_write(&mix,output,n))ok=0;
        for(i=0;i<n*(unsigned)channels;++i)if(!isfinite(output[i])||fabs(output[i])>=.95)ok=0;
        for(c=0;c<VSL_OBJECTS;++c) {
            for(i=0;i<n;++i)mono[i]=sources[i*VSL_OBJECTS+c];
            if(!vsl_wav_write(&stems[c],mono,n))ok=0;
        }
        for(c=0;c<VSL_BRIDGE_GAINS;++c) {
            for(i=0;i<n;++i) { pair[2*i]=pairs[(i*VSL_BRIDGE_GAINS+c)*2];pair[2*i+1]=pairs[(i*VSL_BRIDGE_GAINS+c)*2+1]; }
            if(!vsl_wav_write(&gains[c],pair,n))ok=0;
        }
        vsl_trace_frame(trace,e,e->frame/(double)take.sample_rate);if(!ok)break;
    }
    if(e->frame!=take.frames||(!mode&&channels==2&&player.audio_hash!=take.audio_hash))ok=0;
    snprintf(path,sizeof path,"%s_bridge.json",argv[2]);meta=vsl_fopen(path,"w");if(!meta)goto done;
    fprintf(meta,"{\"schema\":\"vsl.gain-bridge/1\",\"base_runtime\":\"%s\",\"enabled\":%s,\"period_samples\":%u,\"gains\":[",VSL_VERSION,mode?"true":"false",bridge.period);
    for(c=0;c<VSL_BRIDGE_GAINS;++c)fprintf(meta,"%s{\"name\":\"%s\",\"maximum_held_step\":%.17g,\"maximum_ramp_step\":%.17g}",c?",":"",vsl_gain_bridge_name(c),bridge.maximum_held_step[c],bridge.maximum_ramp_step[c]);
    fprintf(meta,"],\"gain_WAV_channels\":[\"native held control gain\",\"causal linear ramp gain\"],\"semantics\":\"Gain WAVs are diagnostic control values, not speaker audio. Ramp reaches current control target at end of period, uses no future inputs. Native control voice restored after each sample. Other voice controls remain held.\"}\n");
    snprintf(path,sizeof path,"%s_scene.json",argv[2]);
    { char prefix[4096];snprintf(prefix,sizeof prefix,"%s_source",argv[2]);if(!vsl_write_scene_metadata(path,&e->target,channels,prefix))ok=0; }
    printf("gain_bridge_v1 | native %s | mode %d | frames %" PRIu64 " | channels %d | hash %016" PRIx64 " | %s\n",VSL_VERSION,mode,e->frame,channels,player.audio_hash,ok?"pass":"FAIL");
done:
    if(meta) { if(ferror(meta))ok=0;if(fclose(meta))ok=0; }
    if(trace) { if(ferror(trace))ok=0;if(fclose(trace))ok=0; }
    if(mix.file)ok=vsl_wav_end(&mix)&&ok;
    for(c=0;c<VSL_OBJECTS;++c)if(stems[c].file)ok=vsl_wav_end(&stems[c])&&ok;
    for(c=0;c<VSL_BRIDGE_GAINS;++c)if(gains[c].file)ok=vsl_wav_end(&gains[c])&&ok;
    vsl_take_free(&take);free(e);return ok?0:2;
}

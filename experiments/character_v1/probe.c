#define _CRT_SECURE_NO_WARNINGS
#include "character.h"
#include "io/take_file.h"
#include "io/wav.h"
#include "io/file.h"
#include "io/drive_trace.h"
#include "io/scene_metadata.h"
#include "drive/scenarios.h"
#include "spatial/scene.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <inttypes.h>
#ifdef _WIN32
#include <windows.h>
#endif
static int number(const char *text,double lo,double hi,double *value) {
    char *end;*value=strtod(text,&end);return *text&&!*end&&isfinite(*value)&&*value>=lo&&*value<=hi;
}
static int capture(int argc,char **argv) {
    VslTake take={0};VslEngine *e=NULL;VslParams p;float audio[1024];
    double seconds,rpm,load,profile,pure;uint64_t frames;int scenario,ok=0;char path[4096];
    if(argc!=9||strlen(argv[2])>3800)return 1;
    scenario=vsl_scenario_id(argv[3]);
    if(scenario<0||!number(argv[4],.1,60,&seconds)||!number(argv[5],0,10000,&rpm)||
       !number(argv[6],-1,1,&load)||!number(argv[7],0,4,&profile)||profile!=floor(profile)||
       !number(argv[8],0,1,&pure)||pure!=floor(pure))return 1;
    p=vsl_default_params((int)profile);p.rpm=rpm;p.load=load;p.pure_osc=(int)pure;
    e=malloc(sizeof *e);if(!e||!vsl_take_allocate(&take,20000))goto done;
    vsl_init(e,48000,48271);vsl_set_params(e,&p);frames=(uint64_t)(seconds*48000+.5);
    if(!vsl_take_begin(&take,e))goto done;
    vsl_character_bind(NULL);
    while(e->frame<frames) {
        unsigned n=(unsigned)(frames-e->frame);if(n>512)n=512;
        vsl_scenario_apply(scenario,e->frame/48000.,&p);vsl_set_params(e,&p);
        if(!vsl_take_record(&take,e->frame,&e->target))goto done;
        vsl_process(e,audio,n);vsl_take_commit(&take,audio,n);
    }
    vsl_take_finish(&take);snprintf(path,sizeof path,"%s.vsltake",argv[2]);
    if(!vsl_take_save(path,&take))goto done;
    printf("Unmodified base %s | frames %" PRIu64 " | input events %u | hash %016" PRIx64 "\n",VSL_VERSION,take.frames,take.count,take.audio_hash);ok=1;
done:vsl_take_free(&take);free(e);return ok?0:2;
}
static int render(int argc,char **argv) {
    VslTake take={0};VslTakePlayer player;VslCharacter state;VslEngine *e=NULL;
    VslWavWriter mix={0},stems[VSL_OBJECTS]={0},parts[3]={0};
    float output[512*12],sources[512*VSL_OBJECTS],detail[512*3],mono[512];
    double pressure,structure,layout;int channels,c,ok=0;FILE *trace=NULL,*events=NULL;
    char path[4096];unsigned n=0,i;uint64_t hash=0;
    const char *partnames[]={"pressure_left","pressure_right","structure_added"};
    if(argc!=7||strlen(argv[3])>3800||!number(argv[4],0,1,&pressure)||
        !number(argv[5],0,1,&structure)||!number(argv[6],2,12,&layout)||(layout!=2&&layout!=12))return 1;
    channels=(int)layout;e=malloc(sizeof *e);if(!e||!vsl_take_load(argv[2],&take)||!vsl_take_player_init(&player,e,&take))goto done;
    vsl_character_init(&state,e,pressure,structure,take.seed);vsl_character_bind(&state);
    snprintf(path,sizeof path,"%s.wav",argv[3]);if(!vsl_wav_begin_float(&mix,path,take.sample_rate,channels))goto done;
    snprintf(path,sizeof path,"%s.csv",argv[3]);trace=vsl_fopen(path,"w");if(!trace)goto done;vsl_trace_header(trace);
    snprintf(path,sizeof path,"%s_character.csv",argv[3]);events=vsl_fopen(path,"w");if(!events)goto done;
    fputs("seconds,rpm,lifecycle,fuel_command,event_count,pressure_left,pressure_right,structure_added,energy_min,energy_max\n",events);
    for(c=0;c<VSL_OBJECTS;++c) {
        snprintf(path,sizeof path,"%s_source_%s.wav",argv[3],vsl_object_info(c)->name);
        if(!vsl_wav_begin_float(&stems[c],path,take.sample_rate,1))goto done;
    }
    for(c=0;c<3;++c) {
        snprintf(path,sizeof path,"%s_part_%s.wav",argv[3],partnames[c]);
        if(!vsl_wav_begin_float(&parts[c],path,take.sample_rate,1))goto done;
    }
    ok=1;
    while(e->frame<take.frames) {
        unsigned got=vsl_take_process(&player,e,output+n*channels,1,channels,sources+n*VSL_OBJECTS);
        if(got!=1) { ok=0;break; }
        for(c=0;c<3;++c)detail[n*3+c]=(float)state.added[c];++n;
        if(e->frame%e->control_period==0) {
            vsl_trace_frame(trace,e,e->frame/(double)take.sample_rate);
            fprintf(events,"%.9f,%.9f,%d,%.9f,%u,%.12g,%.12g,%.12g,%.12g,%.12g\n",
                e->frame/(double)take.sample_rate,e->control.rpm,e->drive.lifecycle,e->drive.fuel.command,
                vsl_character_events(&state),state.added[0],state.added[1],state.added[2],state.energy_min,state.energy_max);
        }
        if(n==512||e->frame==take.frames) {
            if(!vsl_wav_write(&mix,output,n))ok=0;
            for(c=0;c<VSL_OBJECTS;++c) {
                for(i=0;i<n;++i)mono[i]=sources[i*VSL_OBJECTS+c];if(!vsl_wav_write(&stems[c],mono,n))ok=0;
            }
            for(c=0;c<3;++c) {
                for(i=0;i<n;++i)mono[i]=detail[i*3+c];if(!vsl_wav_write(&parts[c],mono,n))ok=0;
            }
            n=0;if(!ok)break;
        }
    }
    hash=player.audio_hash;
    if(e->frame!=take.frames||(channels==2&&pressure==0&&structure==0&&hash!=take.audio_hash))ok=0;
    if(channels==12) {
        char stems_prefix[4096];snprintf(stems_prefix,sizeof stems_prefix,"%s_source",argv[3]);
        snprintf(path,sizeof path,"%s_scene.json",argv[3]);
        if(!vsl_write_scene_metadata(path,&e->target,channels,stems_prefix))ok=0;
    }
    printf("Experimental character_v1 + base %s | frames %" PRIu64 " | channels %d | stroke events %u | hash %016" PRIx64 " | %s\n",
        VSL_VERSION,e->frame,channels,vsl_character_events(&state),hash,ok?"pass":"FAIL");
done:
    vsl_character_bind(NULL);
    if(trace) { if(ferror(trace))ok=0;if(fclose(trace))ok=0; }
    if(events) { if(ferror(events))ok=0;if(fclose(events))ok=0; }
    if(mix.file)ok=vsl_wav_end(&mix)&&ok;
    for(c=0;c<VSL_OBJECTS;++c)if(stems[c].file)ok=vsl_wav_end(&stems[c])&&ok;
    for(c=0;c<3;++c)if(parts[c].file)ok=vsl_wav_end(&parts[c])&&ok;
    free(e);vsl_take_free(&take);return ok?0:2;
}
static int run(int argc,char **argv) {
    if(argc>1&&!strcmp(argv[1],"capture"))return capture(argc,argv);
    if(argc>1&&!strcmp(argv[1],"render"))return render(argc,argv);
    fputs("capture prefix scenario seconds rpm load profile pure\nrender input.vsltake prefix pressure_amount structure_amount channels\n",stderr);return 1;
}
#ifdef _WIN32
int wmain(int argc,wchar_t **wide) {
    char **args=calloc((size_t)argc,sizeof *args);int i,result=2;if(!args)return 2;
    for(i=0;i<argc;++i) {
        int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);args[i]=malloc(n);
        if(!args[i])goto done;WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],n,NULL,NULL);
    }
    result=run(argc,args);
done:for(i=0;i<argc;++i)free(args[i]);free(args);return result;
}
#else
int main(int argc,char **argv) { return run(argc,argv); }
#endif

/* Identical semantic inputs against frozen/current libraries, no take rewriting. */
#include "core/engine.h"
#include "core/character.h"
#include "io/wav.h"
#include "io/file.h"
#include "io/drive_trace.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv) {
    VslEngine *e=NULL;VslParams p=vsl_default_params(VSL_V10);
    VslWavWriter wav={0},mechanical={0};FILE *trace=NULL,*summary=NULL;
    float audio[240*2],stems[240*VSL_OBJECTS],mono[240];char path[4096];
    unsigned block,i,invalid=0,invalid_blocks=0,rotating=0;int ok=0;
    if(argc!=3||strlen(argv[1])>3800||
       (strcmp(argv[2],"cut")&&strcmp(argv[2],"shutdown")&&strcmp(argv[2],"steady")))return 1;
    e=malloc(sizeof *e);if(!e)return 2;
    vsl_init(e,48000,48271);p.rpm=5000;p.load=.85;p.space=0;p.backfire=0;
    p.pressure_texture=p.structure_transfer=.65;
    snprintf(path,sizeof path,"%s.wav",argv[1]);if(!vsl_wav_begin_float(&wav,path,48000,2))goto done;
    snprintf(path,sizeof path,"%s_mechanical.wav",argv[1]);if(!vsl_wav_begin_float(&mechanical,path,48000,1))goto done;
    snprintf(path,sizeof path,"%s.csv",argv[1]);trace=vsl_fopen(path,"w");if(!trace)goto done;vsl_trace_header(trace);
    for(block=0;block<800;++block) {
        unsigned before=e->mechanical.fired_strikes,old_rotating=e->mechanical.rotating_strikes;
        int allowed;
        if(!strcmp(argv[2],"cut"))p.load=block>=400&&block<600?-.4:.85;
        if(!strcmp(argv[2],"shutdown")&&block>=400)p.ignition=0;
        vsl_set_params(e,&p);if(!vsl_process_layout(e,audio,240,2,stems))goto done;
        allowed=(e->drive.lifecycle==VSL_RUNNING||e->drive.lifecycle==VSL_CATCH)&&
            e->drive.combustion>0&&e->drive.fuel.command>0;
        if(!allowed) {
            unsigned delta=e->mechanical.fired_strikes-before;
            invalid+=delta;if(delta)++invalid_blocks;
            rotating+=e->mechanical.rotating_strikes-old_rotating;
        }
        for(i=0;i<240;++i)mono[i]=stems[i*VSL_OBJECTS+VSL_MECHANICAL];
        if(!vsl_wav_write(&wav,audio,240)||!vsl_wav_write(&mechanical,mono,240))goto done;
        vsl_trace_frame(trace,e,e->frame/48000.);
    }
    snprintf(path,sizeof path,"%s.json",argv[1]);summary=vsl_fopen(path,"w");if(!summary)goto done;
    fprintf(summary,"{\"dsp\":\"%s\",\"scenario\":\"%s\",\"disallowed_fired_strikes\":%u,\"blocks_with_disallowed_strikes\":%u,\"rotational_strikes_without_fire_permission\":%u,\"total_fired_strikes\":%u,\"character_events\":%u}\n",
        VSL_VERSION,argv[2],invalid,invalid_blocks,rotating,e->mechanical.fired_strikes,vsl_character_events(&e->character));
    printf("DSP %s | %s | disallowed fired %u | rotational while not firing %u\n",VSL_VERSION,argv[2],invalid,rotating);ok=1;
done:
    if(trace) { if(ferror(trace))ok=0;if(fclose(trace))ok=0; }
    if(summary) { if(ferror(summary))ok=0;if(fclose(summary))ok=0; }
    if(wav.file)ok=vsl_wav_end(&wav)&&ok;if(mechanical.file)ok=vsl_wav_end(&mechanical)&&ok;
    free(e);return ok?0:2;
}

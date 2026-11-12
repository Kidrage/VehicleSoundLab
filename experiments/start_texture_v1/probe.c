#define _CRT_SECURE_NO_WARNINGS
#include "start_texture/voice.h"
#include "core/engine.h"
#include "core/modules.h"
#include "drive/drive.h"
#include "io/wav.h"
#include "io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static StVoice voice;static StProfile profile;static VslEngine engine;
static int free_path(const char *name){FILE *f=vsl_fopen(name,"rb");if(f){fclose(f);return 0;}return 1;}
int main(int argc,char **argv) {
    VslWavWriter wav={0},raw_wav={0};FILE *f,*trace;unsigned n,used=0;int mode;
    unsigned long long seed;char extra;double peak=0;
    float block[480*2],raw_block[480*2];
    if(argc!=8||sscanf(argv[7],"%llu %c",&seed,&extra)!=1)return 1;
    mode=!strcmp(argv[2],"new")?1:!strcmp(argv[2],"old")?0:!strcmp(argv[2],"held")?2:-1;
    if(mode<0)return 1;
    if(!free_path(argv[3])||!free_path(argv[4])||!free_path(argv[5]))return 2;
    /* Sixth argument is reserved explicit duration, not an inferred physical timestamp. */
    {double seconds;if(sscanf(argv[6],"%lf %c",&seconds,&extra)!=1||seconds!=4)return 1;}
    f=vsl_fopen(argv[1],"rb");if(!f)return 2;
    if(!st_profile_read(f,&profile)){fclose(f);return 2;}fclose(f);
    if(!st_voice_init(&voice,&profile,(uint64_t)seed,1))return 3;
    vsl_init(&engine,48000,48271);engine.target=engine.smooth=vsl_default_params(VSL_V10);
    engine.target.ignition=0;engine.target.start_id=0;engine.target.backfire=0;
    engine.target.drive_mode=VSL_BENCH;engine.target.gear=0;
    if(!vsl_wav_begin_float(&wav,argv[3],48000,2)||!vsl_wav_begin_float(&raw_wav,argv[4],48000,2))return 4;
    trace=vsl_fopen(argv[5],"wb");if(!trace)return 4;
    fputs("frame,lifecycle,rpm,start_events,gate,new_envelope\n",trace);
    for(n=0;n<192000;++n) {
        double out[2],raw[2],event;unsigned c;int gate;
        if(n%240==0) {
            engine.target.ignition=(n>=4800&&n<86400)||n>=115200;
            engine.target.start_id=n>=120000?2:n>=7200?1:0;
            vsl_drive_step(&engine.drive,&engine.target,.005);
            vsl_orchestrate(&engine,.005);vsl_events_update(&engine);
        }
        event=vsl_events_tick(&engine);
        gate=mode==2?(n>=7200&&n<163200):engine.drive.lifecycle==VSL_CRANK;
        if(!st_voice_set(&voice,gate,1)||!st_voice_process(&voice,out,raw,1))return 5;
        if(mode==0)out[0]=out[1]=event;
        if(n%240==0)fprintf(trace,"%u,%d,%.17g,%u,%d,%.17g\n",n,engine.drive.lifecycle,engine.drive.rpm,
                           engine.drive.start_events,gate,voice.envelope);
        for(c=0;c<2;++c) {
            if(!isfinite(out[c]))return 5;
            block[2*used+c]=(float)out[c];raw_block[2*used+c]=(float)raw[c];
            peak=fmax(peak,fabs(out[c]));
        }
        if(++used==480) {if(!vsl_wav_write(&wav,block,used)||!vsl_wav_write(&raw_wav,raw_block,used))return 6;used=0;}
        ++engine.frame;
    }
    if(ferror(trace)||fclose(trace)||!vsl_wav_end(&wav)||!vsl_wav_end(&raw_wav))return 6;
    printf("frames=192000 peak=%.17g starts=%u controller=existing sample_playback=0\n",peak,engine.drive.start_events);return 0;
}

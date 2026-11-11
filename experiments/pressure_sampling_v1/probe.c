/* Controlled constant-strength events through unchanged native pressure modes.
   Two observation banks are independent; propagation delay is explicitly zero. */
#include "core/pressure_texture.h"
#include "core/engine.h"
#include "profiles/firing.h"
#include "io/wav.h"
#include "io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv) {
    VslCharacterPressure pressure;VslWavWriter wav={0};FILE *meta=NULL;
    const VslCharacterProfile *p=vsl_character_profile();const VslProfile *engine=vsl_profile(VSL_V10);
    double next[10],offset[10],rpm,cycle;unsigned events[10]={0};long sr;
    unsigned i,frames,warm;int c,k,ok=0;char *end,path[4096];
    if(argc!=4||strlen(argv[1])>3800)return 1;
    sr=strtol(argv[2],&end,10);if(end==argv[2]||*end||sr<16000||sr>192000)return 1;
    rpm=strtod(argv[3],&end);if(end==argv[3]||*end||!isfinite(rpm)||rpm<100||rpm>10000)return 1;
    cycle=rpm/120.;frames=(unsigned)(.6*sr+.5);warm=frames;
    vsl_character_pressure_init(&pressure,(double)sr);
    for(c=0;c<10;++c)next[c]=offset[c]=vsl_firing_degrees(VSL_V10,c,10)/720./cycle;
    if(!vsl_wav_begin_float(&wav,argv[1],(unsigned)sr,2))goto done;
    for(i=0;i<warm+frames;++i) {
        double time=i/(double)sr,output[2];float stereo[2];
        vsl_character_pressure_advance(&pressure);
        for(c=0;c<10;++c)if(next[c]<=time+1e-12) {
            double elapsed=fmax(0,time-next[c]);
            double gain=p->pressure_level*(1+.04*sin(c*1.7));
            vsl_character_pressure_strike(&pressure,engine->bank[c],gain,0,elapsed);
            ++events[c];next[c]=offset[c]+events[c]/cycle;
        }
        vsl_character_pressure_read(&pressure,0,output);
        stereo[0]=(float)output[0];stereo[1]=(float)output[1];
        if(i>=warm&&!vsl_wav_write(&wav,stereo,1))goto done;
    }
    snprintf(path,sizeof path,"%s.json",argv[1]);meta=vsl_fopen(path,"w");if(!meta)goto done;
    fprintf(meta,"{\"dsp\":\"%s\",\"sample_rate\":%ld,\"engineering_rpm\":%.17g,\"cycle_hz\":%.17g,\"warmup_seconds\":%.17g,\"frames\":%u,\"pressure_level\":%.17g,\"modes\":[",VSL_VERSION,sr,rpm,cycle,warm/(double)sr,frames,p->pressure_level);
    for(k=0;k<VSL_CHARACTER_PRESSURE_MODES;++k)
        fprintf(meta,"%s{\"hz\":%.17g,\"decay_seconds\":%.17g,\"weight\":%.17g,\"enabled\":%s}",k?",":"",p->pressure[k].hz,p->pressure[k].decay,p->pressure[k].weight,pressure.mode[0][k].hz?"true":"false");
    fprintf(meta,"],\"events\":[");
    for(c=0;c<10;++c)fprintf(meta,"%s{\"cylinder\":%d,\"bank\":%d,\"cycle_fraction\":%.17g,\"strength\":%.17g,\"count\":%u}",c?",":"",c,engine->bank[c],offset[c]*cycle,1+.04*sin(c*1.7),events[c]);
    fprintf(meta,"],\"scope\":\"Controlled constant-RPM pressure module,shape0,no randomness,no envelope/drive integration,no right-bank delay,no master/IR/spatial path. Actual modes and firing geometry exported from frozen C.\"}\n");ok=1;
done:
    if(meta) { if(ferror(meta))ok=0;if(fclose(meta))ok=0; }
    if(wav.file)ok=vsl_wav_end(&wav)&&ok;
    return ok?0:2;
}

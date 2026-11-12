#define _CRT_SECURE_NO_WARNINGS
#include "resonant_detail_io/profile.h"
#include "resonant_detail/voice.h"
#include "io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
static RdtProfile profile;
static RdtVoice voice;
int main(int argc,char **argv) {
    unsigned frames,n,b;unsigned long long seed;char extra;FILE *file;
    double phase_start,peak=0;
    if(argc!=6||sscanf(argv[3],"%u %c",&frames,&extra)!=1||!frames||frames>2880000||
       sscanf(argv[4],"%llu %c",&seed,&extra)!=1||sscanf(argv[5],"%lf %c",&phase_start,&extra)!=1||
       !isfinite(phase_start)||fabs(phase_start)>1e6) {
        fputs("profile.rdetail output.f64 frames seed starting_phase_cycles\n",stderr);return 1;
    }
    if(!rdt_profile_load(argv[1],&profile)||!rdt_voice_init(&voice,&profile,(uint64_t)seed))return 2;
    file=vsl_fopen(argv[2],"wb");if(!file)return 3;
    for(n=0;n<frames;++n) {
        double row[RDT_MAX_BANDS+2],phase=fmod(phase_start+(double)n*profile.base_hz/48000,1);
        if(phase<0)phase+=1;
        if(!rdt_voice_tick(&voice,phase,row,row+2)) {fclose(file);return 4;}
        for(b=0;b<profile.count+2;++b) {
            if(!isfinite(row[b])){fclose(file);return 5;}
            if(fabs(row[b])>peak)peak=fabs(row[b]);
        }
        if(fwrite(row,sizeof(double),profile.count+2,file)!=profile.count+2){fclose(file);return 6;}
    }
    if(fclose(file))return 6;
    printf("frames=%u bands=%u channels=%u peak=%.17g\n",frames,profile.count,profile.count+2,peak);
    return 0;
}

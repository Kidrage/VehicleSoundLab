#define _CRT_SECURE_NO_WARNINGS
#include "stereo_resonance_io/profile.h"
#include "stereo_resonance/voice.h"
#include "io/file.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif
static RvsProfile profile;static RvsVoice voice;
static double now(void) {
#ifdef _WIN32
    LARGE_INTEGER t,f;QueryPerformanceCounter(&t);QueryPerformanceFrequency(&f);return (double)t.QuadPart/(double)f.QuadPart;
#else
    return (double)clock()/CLOCKS_PER_SEC;
#endif
}
int main(int argc,char **argv) {
    unsigned frames,n,at=0;unsigned long long seed;double amount,total=0,maximum=0;char extra;FILE *file;
    if(argc!=6||sscanf(argv[3],"%llu %c",&seed,&extra)!=1||sscanf(argv[4],"%u %c",&frames,&extra)!=1||
       !frames||frames>2880000||sscanf(argv[5],"%lf %c",&amount,&extra)!=1||
       !rvs_profile_load(argv[1],&profile)||!rvs_voice_init(&voice,&profile,(uint64_t)seed,amount))return 2;
    file=vsl_fopen(argv[2],"wb");if(!file)return 3;
    while(at<frames){unsigned count=frames-at;double buffer[512][2],started=now(),elapsed;if(count>512)count=512;
        for(n=0;n<count;++n)if(!rvs_voice_tick(&voice,buffer[n],NULL)){fclose(file);return 4;}
        elapsed=now()-started;total+=elapsed;if(elapsed>maximum)maximum=elapsed;
        if(fwrite(buffer,2*sizeof(double),count,file)!=count){fclose(file);return 4;}at+=count;
    }
    if(fclose(file))return 3;
    printf("{\"frames\":%u,\"generation_wall_seconds\":%.9g,\"maximum_block_ms\":%.9g,\"not_device_test\":true}\n",frames,total,maximum*1000);
    return 0;
}

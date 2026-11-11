#define _CRT_SECURE_NO_WARNINGS
#include "oscillator.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>
#include <inttypes.h>
int main(int argc,char **argv) {
    RoModel model={0};RoPlayer player;VslWavWriter writer={0},high_writer={0};
    double data[257*2],high[257*2],amount;float out[257*2],high_out[257*2];char *end;
    unsigned n,i;uint64_t frames=0;int ok=0;clock_t start;
    if(argc!=5)return 1;
    amount=strtod(argv[4],&end);if(end==argv[4]||*end||!isfinite(amount)||amount<0||amount>1)return 1;
    if(!ro_model_load(argv[1],&model)||!ro_player_init(&player,&model,amount))goto done;
    if(!vsl_wav_begin_float(&writer,argv[2],model.rate,2)||!vsl_wav_begin_float(&high_writer,argv[3],model.rate,2))goto done;
    start=clock();
    while((n=ro_process(&player,data,high,257))!=0) {
        for(i=0;i<n*2;++i) { if(!isfinite(data[i])||!isfinite(high[i]))goto done;out[i]=(float)data[i];high_out[i]=(float)high[i]; }
        if(!vsl_wav_write(&writer,out,n)||!vsl_wav_write(&high_writer,high_out,n))goto done;
        frames+=n;
    }
    printf("ReferenceOSC1 | frames%" PRIu64 " | coefficient_segments%u | high_amount%.3f | CPU_seconds%.6f\n",frames,model.count,amount,(clock()-start)/(double)CLOCKS_PER_SEC);
    ok=frames==model.frames;
done:
    if(writer.file)ok=vsl_wav_end(&writer)&&ok;
    if(high_writer.file)ok=vsl_wav_end(&high_writer)&&ok;
    ro_model_free(&model);return ok?0:2;
}

#define _CRT_SECURE_NO_WARNINGS
#include "pitch.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <inttypes.h>
int main(int argc,char **argv) {
    RoModel model={0};RtTracks tracks={0};RtPlayer player={0};VslWavWriter wav={0};
    double x[514],pitch,high;float y[514];unsigned n,i;uint64_t count=0;char *end;int ok=0;
    if(argc!=6)return 1;
    pitch=strtod(argv[4],&end);if(end==argv[4]||*end||!isfinite(pitch))return 1;
    high=strtod(argv[5],&end);if(end==argv[5]||*end||!isfinite(high))return 1;
    if(!ro_model_load(argv[1],&model)||!rt_tracks_load(argv[2],&model,&tracks)||!rt_player_init(&player,&model,&tracks,pitch,high))goto done;
    if(!vsl_wav_begin_float(&wav,argv[3],model.rate,2))goto done;
    while((n=rt_process(&player,x,257))!=0) {
        for(i=0;i<n*2;++i){if(!isfinite(x[i]))goto done;y[i]=(float)x[i];}
        if(!vsl_wav_write(&wav,y,n))goto done;count+=n;
    }
    ok=count==model.frames;
    printf("TrackedOSC2 | frames%" PRIu64 " | persistent_tracks%u | pitch%.3f | high%.3f\n",count,tracks.tracks,pitch,high);
done:
    if(wav.file)ok=vsl_wav_end(&wav)&&ok;
    rt_player_free(&player);rt_tracks_free(&tracks);ro_model_free(&model);return ok?0:2;
}

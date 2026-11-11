#define _CRT_SECURE_NO_WARNINGS
#include "sound_residual/voice.h"
#include "io/file.h"
#include "io/wav.h"
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <windows.h>
#endif
static SrVoice voice;
static int run(int argc,char **argv) {
    SrProfile p;VslWavWriter wav={0};FILE *stream;char *end;double seconds,pitch,gain,raw[1024];float pcm[1024];
    unsigned frames,at=0,n,i;uint64_t seed;int ok=0;
    if(argc!=7)return 1;
    seconds=strtod(argv[3],&end);if(end==argv[3]||*end||!isfinite(seconds)||seconds<=0||seconds>60)return 1;
    pitch=strtod(argv[4],&end);if(end==argv[4]||*end||!isfinite(pitch)||pitch<.9||pitch>1.1)return 1;
    gain=strtod(argv[5],&end);if(end==argv[5]||*end||!isfinite(gain)||gain<0||gain>1)return 1;
    errno=0;seed=strtoull(argv[6],&end,10);if(end==argv[6]||*end||argv[6][0]=='-'||errno==ERANGE)return 1;
    stream=vsl_fopen(argv[1],"rb");if(!stream)return 2;
    ok=sr_profile_read(stream,&p);if(fclose(stream))ok=0;
    if(!ok||!sr_voice_init(&voice,&p,seed,pitch,gain)||!vsl_wav_begin_float(&wav,argv[2],48000,2))return 2;
    frames=(unsigned)(seconds*48000+.5);ok=1;
    while(at<frames) {
        n=frames-at;if(n>512)n=512;
        if(!sr_voice_process(&voice,raw,n)){ok=0;break;}
        for(i=0;i<2*n;++i)pcm[i]=(float)raw[i];
        if(!vsl_wav_write(&wav,pcm,n)){ok=0;break;}at+=n;
    }
    if(!vsl_wav_end(&wav))ok=0;return ok?0:3;
}
#ifdef _WIN32
int wmain(int argc,wchar_t **wide) {
    char **args=calloc((size_t)argc,sizeof *args);int i,result=2;if(!args)return 2;
    for(i=0;i<argc;++i) {
        int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        if(!n||!(args[i]=malloc((size_t)n))||!WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],n,NULL,NULL))goto done;
    }
    result=run(argc,args);
done:for(i=0;i<argc;++i)free(args[i]);free(args);return result;
}
#else
int main(int argc,char **argv){return run(argc,argv);}
#endif

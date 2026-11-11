#define _CRT_SECURE_NO_WARNINGS
#include "dna_atlas/voice.h"
#include "osc_colour/profile.h"
#include "osc_colour/envelope.h"
#include "io/file.h"
#include "io/wav.h"
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif
static SdProfile model;
static SaBank bank;
static SaVoice voice;
static int number(const char *text,double low,double high,double *v) {
    char *end;errno=0;*v=strtod(text,&end);
    return end!=text&&!*end&&errno!=ERANGE&&isfinite(*v)&&*v>=low&&*v<=high;
}
static int run(int argc,char **argv) {
    OcProfile colour;OcEnvelope envelope;HbBand band=hb_band_default();
    const SdProfile *models[]={&model};VslWavWriter wav={0};FILE *f;
    double seconds,root,amount=0,gain,g[OC_MAX_HARMONICS],peak=0,energy=0;char *end;
    unsigned frames,at=0,n,i;int transition,ok;uint64_t seed;float pcm[1024];
    if(argc!=9){fprintf(stderr,"model colour output.wav seconds root_hz amount|rise-fall gain seed\n");return 1;}
    transition=!strcmp(argv[6],"rise-fall");
    if(!number(argv[4],.1,60,&seconds)||!number(argv[5],1,1000,&root)||
       (!transition&&!number(argv[6],0,1,&amount))||!number(argv[7],0,1,&gain))return 1;
    errno=0;seed=strtoull(argv[8],&end,10);
    if(end==argv[8]||*end||errno==ERANGE||argv[8][0]=='-')return 1;
    f=vsl_fopen(argv[2],"rb");if(!f)return 2;
    ok=oc_profile_read(f,&colour);if(fclose(f))ok=0;
    if(!ok||!sd_profile_load(argv[1],&model)||!oc_profile_compile(&colour,g,model.harmonics)||
       !sa_bank_init(&bank,models,1,0)||!sa_voice_init(&voice,&bank,seed,root,1,1)||
       !oc_envelope_init(&envelope,amount,.12)||!vsl_wav_begin_float(&wav,argv[3],48000,2))return 2;
    frames=(unsigned)(seconds*48000+.5);ok=1;
    while(at<frames){
        n=frames-at;if(n>512)n=512;
        for(i=0;i<n;++i){double full[2],body[2];unsigned c;
            if(transition)oc_envelope_set(&envelope,at+i>=96000&&at+i<288000?1:0);
            if(!sa_voice_tick_shaped_body(&voice,&band,g,oc_envelope_tick(&envelope),full,body)){ok=0;break;}
            for(c=0;c<2;++c){double x=full[c]*gain;pcm[2*i+c]=(float)x;peak=fmax(peak,fabs(x));energy+=x*x;}
        }
        if(!ok||!vsl_wav_write(&wav,pcm,n)){ok=0;break;}at+=n;
    }
    if(!vsl_wav_end(&wav))ok=0;
    if(ok)printf("{\"frames\":%u,\"root_hz\":%.17g,\"gain\":%.17g,\"peak\":%.17g,\"rms\":%.17g,\"transition\":%s}\n",
        at,root,gain,peak,sqrt(energy/(2*at)),transition?"true":"false");
    return ok?0:3;
}
#ifdef _WIN32
int wmain(int argc,wchar_t **wide) {
    char **args=calloc((size_t)argc,sizeof *args);int i,result=2;if(!args)return 2;
    for(i=0;i<argc;++i){
        int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        if(!n||!(args[i]=malloc((size_t)n))||!WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],n,NULL,NULL))goto done;
    }
    result=run(argc,args);
done:for(i=0;i<argc;++i)free(args[i]);free(args);return result;
}
#else
int main(int argc,char **argv){return run(argc,argv);}
#endif

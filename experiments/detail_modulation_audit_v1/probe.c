/* Read-only inspection of the frozen source, plus an explicitly unaccepted
   phase-fixed ablation. No change to the native monitor or accepted recipe. */
#define _CRT_SECURE_NO_WARNINGS
#include "source.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#define PI 3.14159265358979323846
#define FRAMES 768000u
static SuModel model;static SuSource source,control;
static unsigned orders[]={5,10,15,20,25,30,40,50,60};
static uint64_t hash(uint64_t h,float f){unsigned i;uint32_t bits;memcpy(&bits,&f,4);for(i=0;i<4;++i){h^=(bits>>(8*i))&255;h*=UINT64_C(1099511628211);}return h;}
int main(int argc,char **argv){
    VslWavWriter full={0},radial={0};FILE *trace=NULL,*report=NULL;char path[2048],*end;double amount;
    unsigned n,h,c,j;uint64_t fingerprint=UINT64_C(14695981039346656037);double error=0,clock_error=0;
    double original[2],unused[2],block[512*2],fixed[512*2];float pcm[512*2],radial_pcm[512*2];int ok=0;
    if(argc!=4)return 1;amount=strtod(argv[3],&end);if(end==argv[3]||*end||!isfinite(amount)||amount<0||amount>1)return 1;
    if(!su_model_load(argv[1],&model)||!su_init(&source,&model,48271,1,amount,1)||!su_init(&control,&model,48271,1,1,1))return 2;
    snprintf(path,sizeof path,"%s_full_float.wav",argv[2]);if(!vsl_wav_begin_float(&full,path,48000,2))goto done;
    snprintf(path,sizeof path,"%s_radial_float.wav",argv[2]);if(!vsl_wav_begin_float(&radial,path,48000,2))goto done;
    snprintf(path,sizeof path,"%s_trace.csv",argv[2]);trace=fopen(path,"wb");if(!trace)goto done;
    fprintf(trace,"frame,pitch,amount,carrier_phase,rng");
    for(j=0;j<sizeof orders/sizeof *orders;++j)for(c=0;c<4;++c)fprintf(trace,",h%u_%u",orders[j],c);fprintf(trace,"\n");
    for(n=0;n<FRAMES;++n){double fraction,phase,base_c,base_s,cl,sl,check[2]={0},alt[2]={0};unsigned slot=n%512;
        su_process(&source,original,1);su_process(&control,unused,1);
        clock_error=fmax(clock_error,fabs(source.phase-control.phase)+fabs(source.fraction-control.fraction));
        if(source.rng!=control.rng||source.updates!=control.updates)goto done;
        fraction=source.fraction-source.pitch/model.hop;
        phase=source.phase-2*PI*source.pitch/model.window;
        base_c=cl=cos(phase);base_s=sl=sin(phase);
        for(h=0;h<model.harmonics;++h){double z[4],next;
            for(c=0;c<4;++c)z[c]=model.harmonic[h].mean[c]+source.amount*(source.left[h][c]+fraction*(source.right[h][c]-source.left[h][c]));
            for(c=0;c<2;++c){double re=z[c*2],im=z[c*2+1],mr=model.harmonic[h].mean[c*2],mi=model.harmonic[h].mean[c*2+1];
                double magnitude=hypot(re,im),mean_magnitude=hypot(mr,mi);
                check[c]+=re*cl-im*sl;
                if(mean_magnitude>1e-15)alt[c]+=magnitude*(mr*cl-mi*sl)/mean_magnitude;
                else alt[c]+=re*cl-im*sl;
            }
            next=sl*base_c+cl*base_s;cl=cl*base_c-sl*base_s;sl=next;
        }
        for(c=0;c<2;++c){error=fmax(error,fabs(check[c]-original[c]));block[slot*2+c]=original[c];fixed[slot*2+c]=alt[c];}
        if(n%48==0){fprintf(trace,"%u,%.17g,%.17g,%.17g,%" PRIu64,n,source.pitch,source.amount,phase,source.rng);
            for(j=0;j<sizeof orders/sizeof *orders;++j){h=orders[j]-1;
                for(c=0;c<4;++c){double z=model.harmonic[h].mean[c]+source.amount*(source.left[h][c]+fraction*(source.right[h][c]-source.left[h][c]));fprintf(trace,",%.17g",z);}}
            fprintf(trace,"\n");}
        if(slot==511){for(j=0;j<1024;++j){pcm[j]=(float)block[j];radial_pcm[j]=(float)fixed[j];fingerprint=hash(fingerprint,pcm[j]);}
            if(!vsl_wav_write(&full,pcm,512)||!vsl_wav_write(&radial,radial_pcm,512))goto done;}
    }
    snprintf(path,sizeof path,"%s_probe.json",argv[2]);report=fopen(path,"wb");if(!report)goto done;
    fprintf(report,"{\"frames\":%u,\"amount\":%.17g,\"pitch\":1,\"clock_error_vs_amount1\":%.17g,\"rng_and_updates_identical\":true,\"coefficient_reconstruction_error\":%.17g,\"raw_float_hash\":\"%016" PRIx64 "\"}\n",FRAMES,amount,clock_error,error,fingerprint);
    ok=error<1e-10&&clock_error==0;
done:
    if(full.file)ok=vsl_wav_end(&full)&&ok;if(radial.file)ok=vsl_wav_end(&radial)&&ok;
    if(trace)fclose(trace);if(report)fclose(report);return ok?0:3;
}

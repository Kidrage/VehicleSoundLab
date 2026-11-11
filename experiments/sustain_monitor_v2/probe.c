#define _CRT_SECURE_NO_WARNINGS
#include "render.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
static SuModel model;static LbProfile body;static SmRender mixed,base;
int main(int argc,char **argv){
    VslWavWriter w={0},stem={0};char path[2048],*end;double amount,detail;unsigned i,j;
    float raw[1024],output[1024],base_raw[1024],base_output[1024],body_output[1024];int ok=0;
    if(argc!=6)return 1;
    detail=strtod(argv[4],&end);if(end==argv[4]||*end||!isfinite(detail)||detail<0||detail>1)return 1;
    amount=strtod(argv[5],&end);if(end==argv[5]||*end||!isfinite(amount)||amount<0||amount>1)return 1;
    if(!su_model_load(argv[1],&model)||!lb_profile_load(argv[2],&body)||!sm_render_init(&mixed,&model,1000,(int)(detail*1000+.5),0)||!sm_render_init(&base,&model,1000,(int)(detail*1000+.5),0)||!sm_render_body_init(&mixed,&body,amount))return 2;
    snprintf(path,sizeof path,"%s_mix_float.wav",argv[3]);if(!vsl_wav_begin_float(&w,path,48000,2))goto done;
    snprintf(path,sizeof path,"%s_body_float.wav",argv[3]);if(!vsl_wav_begin_float(&stem,path,48000,2))goto done;
    for(i=0;i<384000;i+=512){sm_render_process(&mixed,raw,output,512,0);sm_render_process(&base,base_raw,base_output,512,0);
        for(j=0;j<1024;++j)body_output[j]=output[j]-base_output[j];
        if(!vsl_wav_write(&w,output,512)||!vsl_wav_write(&stem,body_output,512))goto done;
    }ok=1;
done:if(w.file)ok=vsl_wav_end(&w)&&ok;if(stem.file)ok=vsl_wav_end(&stem)&&ok;return ok?0:3;
}

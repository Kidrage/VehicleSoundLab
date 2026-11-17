#define _CRT_SECURE_NO_WARNINGS
#include "bridge.h"
#include "core/types.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv) {
    VsbHandle *h=NULL;VsControl c;VsTelemetry t;VslWavWriter mix={0},stem[VS_STEMS]={{0}};
    float audio[VS_BLOCK_MAX*2],packed[VS_BLOCK_MAX*VS_STEMS*2],native[VS_BLOCK_MAX*2];
    unsigned width=vsl_source_channels();
    unsigned at,n,frames,offset,k,j,ch;char path[4096];int ok=0,selection;double seconds;
    if(argc!=4){fprintf(stderr,"usage: vehicle_source_probe CATALOG_ID OUTPUT_PREFIX SECONDS\n");return 2;}
    selection=atoi(argv[1]);seconds=atof(argv[3]);
    if(!isfinite(seconds)||seconds<1||seconds>120)return 2;
    frames=(unsigned)(seconds*VS_RATE);h=vsl_source_open(selection);if(!h)goto done;
    if(!vsl_source_controls(h,&c))goto done;
    c.ignition=c.start_id=1;if(!vsl_source_set(h,&c))goto done;
    snprintf(path,sizeof path,"%s_mix.wav",argv[2]);if(!vsl_wav_begin_float(&mix,path,VS_RATE,2))goto done;
    for(k=0;k<VS_STEMS;++k) {
        const VsStemInfo *m=vs_stem_info(k);snprintf(path,sizeof path,"%s_%s.wav",argv[2],m->id);
        if(!vsl_wav_begin_float(stem+k,path,VS_RATE,m->channels))goto done;
    }
    for(at=0;at<frames;at+=n) {
        n=frames-at>VS_BLOCK_MAX?VS_BLOCK_MAX:frames-at;
        if(!vsl_source_process(h,audio,packed,n)||!vsl_wav_write(&mix,audio,n))goto done;
        offset=0;
        for(k=0;k<VS_STEMS;++k) {
            unsigned channels=vs_stem_info(k)->channels;
            for(j=0;j<n;++j)for(ch=0;ch<channels;++ch)native[j*channels+ch]=packed[j*width+offset+ch];
            if(!vsl_wav_write(stem+k,native,n))goto done;offset+=channels;
        }
    }
    if(!vsl_source_state(h,&t))goto done;
    printf("source-only %u frames / %u native stem channels / %.3f RPM; no spatial render\n",frames,vsl_source_channels(),t.rpm);ok=1;
done:
    if(mix.file&&!vsl_wav_end(&mix))ok=0;
    for(k=0;k<VS_STEMS;++k)if(stem[k].file&&!vsl_wav_end(stem+k))ok=0;
    vsl_source_close(h);return ok?0:3;
}

#define _CRT_SECURE_NO_WARNINGS
#include "wav.h"
#include "file.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static void put16(FILE*f,uint16_t x) { unsigned char b[2]={(unsigned char)x,(unsigned char)(x>>8)}; fwrite(b,1,2,f); }
static void put32(FILE*f,uint32_t x) { put16(f,(uint16_t)x); put16(f,(uint16_t)(x>>16)); }
static uint16_t get16(const unsigned char*p) { return (uint16_t)(p[0]|p[1]<<8); }
static uint32_t get32(const unsigned char*p) { return (uint32_t)get16(p)|(uint32_t)get16(p+2)<<16; }
static void header(VslWavWriter*w) {
    FILE*f=w->file;unsigned stride=w->floating?4:2;uint32_t bytes=w->frames*w->channels*stride;
    unsigned ch=w->channels,ext=ch>2||w->floating,code=w->floating?3:1;
    fseek(f,0,SEEK_SET);fwrite("RIFF",1,4,f);put32(f,(ext?60:36)+(w->floating?12:0)+bytes);fwrite("WAVEfmt ",1,8,f);
    put32(f,ext?40:16);put16(f,(uint16_t)(ext?65534:code));put16(f,(uint16_t)ch);
    put32(f,w->sample_rate);put32(f,w->sample_rate*ch*stride);put16(f,(uint16_t)(ch*stride));put16(f,(uint16_t)(stride*8));
    if(ext) {
        /* Ascending WAVE speaker-mask bit order: FL FR FC LFE BL BR SL SR TFL TFR TBL TBR. */
        unsigned char pcm_guid[16]={1,0,0,0,0,0,16,0,128,0,0,170,0,56,155,113};pcm_guid[0]=(unsigned char)code;
        put16(f,22);put16(f,(uint16_t)(stride*8));put32(f,ch==12?0x2d63f:(ch==2?3:4));fwrite(pcm_guid,1,16,f);
    }
    if(w->floating) { fwrite("fact",1,4,f);put32(f,4);put32(f,w->frames); }
    fwrite("data",1,4,f);put32(f,bytes);
}
int vsl_wav_begin(VslWavWriter*w,const char*path,unsigned sr) {
    return vsl_wav_begin_layout(w,path,sr,2);
}
static int begin(VslWavWriter*w,const char*path,unsigned sr,unsigned channels,int floating) {
    if(channels!=1&&channels!=2&&channels!=12)return 0;
    memset(w,0,sizeof *w);w->channels=channels;w->floating=(unsigned)floating;w->file=vsl_fopen(path,"wb");if(!w->file)return 0;
    w->sample_rate=sr; header(w); return !ferror(w->file);
}
int vsl_wav_begin_layout(VslWavWriter*w,const char*path,unsigned sr,unsigned channels) { return begin(w,path,sr,channels,0); }
int vsl_wav_begin_float(VslWavWriter*w,const char*path,unsigned sr,unsigned channels) { return begin(w,path,sr,channels,1); }
int vsl_wav_write(VslWavWriter*w,const float*x,unsigned n) {
    unsigned i;
    if(!w->file)return 0;
    if(((uint64_t)w->frames+n)*w->channels*(w->floating?4u:2u)>UINT32_MAX-128u)return 0;
    for(i=0;i<n*w->channels;++i) {
        if(w->floating) { float v=isfinite(x[i])?x[i]:0;uint32_t bits;memcpy(&bits,&v,4);put32(w->file,bits); }
        else { double v=isfinite(x[i])?x[i]:0;int16_t s=(int16_t)(fmax(-1,fmin(1,v))*32767);put16(w->file,(uint16_t)s); }
    }
    w->frames+=n; return !ferror(w->file);
}
int vsl_wav_end(VslWavWriter*w) { int ok; if(!w->file)return 0; header(w); ok=!ferror(w->file); if(fclose(w->file))ok=0; w->file=NULL; return ok; }
float *vsl_wav_read(const char*path,unsigned*frames,unsigned*sr) {
    FILE*f=vsl_fopen(path,"rb"); unsigned char h[16],fmt[40]={0};
    unsigned bytes=0,code=0,ch=0,bits=0,rate=0,align=0,i; long data_pos=0;
    float*out=NULL;
    *frames=0; *sr=0;
    if(!f)return NULL;
    if(fread(h,1,12,f)!=12 || memcmp(h,"RIFF",4)||memcmp(h+8,"WAVE",4))goto done;
    while(fread(h,1,8,f)==8) {
        uint32_t size=get32(h+4); long pos=ftell(f);
        if(size>512*1024*1024u)goto done;
        if(!memcmp(h,"fmt ",4)) {
            if(size<16 || fread(fmt,1,size<40?size:40,f)<16)goto done;
            code=get16(fmt); ch=get16(fmt+2); rate=get32(fmt+4); align=get16(fmt+12); bits=get16(fmt+14);
            if(code==65534 && size>=40)code=get16(fmt+24);
        } else if(!memcmp(h,"data",4)) { data_pos=pos; bytes=size; }
        if(fseek(f,pos+size+(size&1),SEEK_SET))goto done;
        if(data_pos && rate)break;
    }
    if(!data_pos || !bytes || (ch!=1&&ch!=2) || rate<8000 || rate>192000 ||
       !((code==1&&(bits==16||bits==24||bits==32))||(code==3&&bits==32)) || align!=ch*bits/8)goto done;
    *frames=bytes/align;
    out=(float*)malloc((size_t)*frames*2*sizeof(float)); if(!out)goto done;
    fseek(f,data_pos,SEEK_SET);
    for(i=0;i<*frames;++i) {
        unsigned c;
        for(c=0;c<ch;++c) {
            float v; unsigned char b[4]={0};
            if(fread(b,1,bits/8,f)!=bits/8) { free(out); out=NULL; goto done; }
            if(code==3)memcpy(&v,b,4);
            else if(bits==16)v=(int16_t)get16(b)/32768.f;
            else if(bits==24) { int32_t s=(int32_t)(b[0]|b[1]<<8|b[2]<<16); if(s&0x800000)s|=(int32_t)0xff000000; v=s/8388608.f; }
            else v=(int32_t)get32(b)/2147483648.f;
            out[2*i+c]=isfinite(v)?fmaxf(-1,fminf(1,v)):0;
        }
        if(ch==1)out[2*i+1]=out[2*i];
    }
    *sr=rate;
done:
    fclose(f); if(!out)*frames=0; return out;
}

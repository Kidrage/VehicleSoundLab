#define _CRT_SECURE_NO_WARNINGS
#include "take_file.h"
#include "file.h"
#include "session/parameters.h"
#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif
static int token(FILE *f,char *s,size_t cap) {
    int c;size_t n=0;do { c=fgetc(f); }while(c!=EOF&&isspace((unsigned char)c));
    if(c==EOF)return 0;
    do { if(n+1>=cap)return 0;s[n++]=(char)c;c=fgetc(f); }while(c!=EOF&&!isspace((unsigned char)c));
    s[n]=0;return 1;
}
static int word(FILE *f,const char *wanted) { char s[128];return token(f,s,sizeof s)&&!strcmp(s,wanted); }
static int natural(FILE *f,uint64_t *v) {
    char s[128],*end;unsigned long long n;
    if(!token(f,s,sizeof s)||!isdigit((unsigned char)s[0]))return 0;
    errno=0;n=strtoull(s,&end,10);if(errno||*end)return 0;*v=(uint64_t)n;return 1;
}
static int real(FILE *f,double *v) {
    char s[128],*end;if(!token(f,s,sizeof s))return 0;
    errno=0;*v=strtod(s,&end);return end!=s&&!*end&&errno!=ERANGE&&isfinite(*v);
}
static int bounded(FILE *f,unsigned *v,unsigned max) {
    uint64_t n;if(!natural(f,&n)||n>max)return 0;*v=(unsigned)n;return 1;
}
static int remove_utf8(const char *path) {
#ifdef _WIN32
    wchar_t w[32768];if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,w,32768))return 0;
    return DeleteFileW(w)!=0;
#else
    return remove(path)==0;
#endif
}
static int replace_utf8(const char *from,const char *to) {
#ifdef _WIN32
    wchar_t a[32768],b[32768];
    if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,from,-1,a,32768)||!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,to,-1,b,32768))return 0;
    return MoveFileExW(a,b,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=0;
#else
    return rename(from,to)==0;
#endif
}
int vsl_take_save(const char *path,const VslTake *t) {
    FILE *f=NULL;char temp[4096];unsigned i,j,n,attempt;int ok;
    const VslParamField *fields=vsl_take_fields(&n);
    if(!path||strlen(path)>4000||!vsl_take_validate(t))return 0;
    for(attempt=0;attempt<100&&!f;++attempt) {
        snprintf(temp,sizeof temp,"%s.tmp.%llu.%u",path,(unsigned long long)time(NULL),attempt);
        f=vsl_fopen(temp,"wbx");
    }
    if(!f)return 0;
    fprintf(f,"VSLTAKE 5\ndsp %s\nsample_rate %u\nseed %u\nframes %" PRIu64 "\naudio_hash %" PRIu64 "\nfields %u",t->dsp,t->sample_rate,t->seed,t->frames,t->audio_hash,n);
    for(i=0;i<n;++i)fprintf(f," %s",fields[i].name);
    fprintf(f,"\ndna %u %.17g\n",t->assets.dna_count,t->assets.dna_root);
    for(i=0;i<t->assets.dna_count;++i)fprintf(f,"%.17g %.17g\n",t->assets.dna_amp[i],t->assets.dna_phase[i]);
    fprintf(f,"ir %u\n",t->assets.ir_length);
    for(i=0;i<t->assets.ir_length;++i)fprintf(f,"%.9g\n",t->assets.ir[i]);
    fprintf(f,"events %u\n",t->count);
    for(i=0;i<t->count;++i) {
        fprintf(f,"event %" PRIu64,t->events[i].frame);
        for(j=0;j<n;++j) {
            const char *at=(const char*)&t->events[i].params+fields[j].offset;
            if(fields[j].integer)fprintf(f," %d",*(const int*)at);else fprintf(f," %.17g",*(const double*)at);
        }
        fputc('\n',f);
    }
    fputs("end\n",f);ok=!ferror(f);if(fclose(f))ok=0;
    if(ok)ok=replace_utf8(temp,path);if(!ok)remove_utf8(temp);return ok;
}
int vsl_take_load(const char *path,VslTake *take) {
    VslTake t={0};FILE *f=vsl_fopen(path,"rb");unsigned i,j,n,count,read_count;uint64_t u;double d;long size;int ok=0,c;
    const VslParamField *fields=vsl_take_fields(&n);
    if(!f)return 0;
    if(fseek(f,0,SEEK_END)||(size=ftell(f))<0||size>64*1024*1024||fseek(f,0,SEEK_SET))goto done;
    if(!word(f,"VSLTAKE")||!word(f,"5")||!word(f,"dsp")||!token(f,t.dsp,sizeof t.dsp)||strcmp(t.dsp,VSL_VERSION)||
       !word(f,"sample_rate")||!bounded(f,&t.sample_rate,48000)||t.sample_rate!=48000||
       !word(f,"seed")||!natural(f,&u)||!u||u>UINT32_MAX)goto done;
    t.seed=(uint32_t)u;
    if(!word(f,"frames")||!natural(f,&t.frames)||!t.frames||t.frames>VSL_TAKE_MAX_FRAMES||
       !word(f,"audio_hash")||!natural(f,&t.audio_hash)||!word(f,"fields")||!bounded(f,&read_count,n)||read_count!=n)goto done;
    for(i=0;i<n;++i)if(!word(f,fields[i].name))goto done;
    if(!word(f,"dna")||!bounded(f,&t.assets.dna_count,VSL_PARTIALS)||!real(f,&t.assets.dna_root))goto done;
    for(i=0;i<t.assets.dna_count;++i)if(!real(f,&t.assets.dna_amp[i])||!real(f,&t.assets.dna_phase[i]))goto done;
    if(!word(f,"ir")||!bounded(f,&t.assets.ir_length,VSL_MAX_IR))goto done;
    for(i=0;i<t.assets.ir_length;++i) { if(!real(f,&d)||fabs(d)>3.402823466e38)goto done;t.assets.ir[i]=(float)d; }
    if(!word(f,"events")||!bounded(f,&count,VSL_TAKE_EVENTS)||!count)goto done;
    t.events=calloc(count,sizeof *t.events);if(!t.events)goto done;t.count=t.capacity=count;
    for(i=0;i<count;++i) {
        if(!word(f,"event")||!natural(f,&t.events[i].frame))goto done;
        for(j=0;j<n;++j) {
            char *at=(char*)&t.events[i].params+fields[j].offset;
            if(fields[j].integer) { if(!natural(f,&u)||u>INT_MAX)goto done;*(int*)at=(int)u; }
            else { if(!real(f,&d))goto done;*(double*)at=d; }
        }
    }
    if(!word(f,"end"))goto done;
    do { c=fgetc(f); }while(c!=EOF&&isspace((unsigned char)c));
    if(c!=EOF||ferror(f)||!vsl_take_validate(&t))goto done;
    vsl_take_free(take);*take=t;memset(&t,0,sizeof t);ok=1;
done:
    vsl_take_free(&t);fclose(f);return ok;
}

#define _CRT_SECURE_NO_WARNINGS
#include "io.h"
#include "io/file.h"
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include "dsp_support/storage.h"
VSL_STORAGE(sf_read_scratch,SfProfile,1,VSL_DDR)
VSL_STORAGE(sf_load_scratch,SfProfile,1,VSL_DDR)
static int integer(FILE *f,unsigned *out) {
    char token[32],*end;unsigned long v;unsigned i;
    if(fscanf(f,"%31s",token)!=1)return 0;for(i=0;token[i];++i)if(!isdigit((unsigned char)token[i]))return 0;
    errno=0;v=strtoul(token,&end,10);if(errno||*end||v>UINT_MAX)return 0;*out=(unsigned)v;return 1;
}
int sf_profile_read(FILE *f,SfProfile *out) {
    SfProfile *p;char tag[32];unsigned version,b,n;int ch,ok=0;
    if(!f||!out)return 0;p=sf_read_scratch_acquire();if(!p)return 0;
    if(fscanf(f,"%31s",tag)!=1||strcmp(tag,"VSL_SPECTRAL_TEXTURE")||!integer(f,&version)||(version!=1&&version!=2)||
       !integer(f,&p->rate)||!integer(f,&p->count)||!p->count||p->count>SF_MAX_BANDS||!integer(f,&p->warmup_frames))goto done;
    for(b=0;b<p->count;++b) {
        SfBand *m=p->band+b;
        if(!integer(f,&m->count)||!m->count||m->count>PF_MAX_TAPS||fscanf(f,"%f %f",&m->gain,&m->right_over_left)!=2)goto done;
        m->decimation=1;
        if(version==2&&!integer(f,&m->decimation))goto done;
        for(n=0;n<m->count;++n)if(fscanf(f,"%f",m->taps+n)!=1)goto done;
    }
    do{ch=fgetc(f);}while(ch!=EOF&&isspace((unsigned char)ch));
    if(ch==EOF&&!ferror(f)&&sf_profile_valid(p)){*out=*p;ok=1;}
done:sf_read_scratch_release(p);return ok;
}
int sf_profile_load(const char *path,SfProfile *out) {
    FILE *f;SfProfile *p;int ok=0;if(!path||!out)return 0;
    f=vsl_fopen(path,"rb");if(!f)return 0;p=sf_load_scratch_acquire();
    if(p)ok=sf_profile_read(f,p);if(fclose(f))ok=0;if(ok)*out=*p;sf_load_scratch_release(p);return ok;
}

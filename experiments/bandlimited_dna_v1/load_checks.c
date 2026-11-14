#define _CRT_SECURE_NO_WARNINGS
#include "test_models.h"
#include "dna_atlas/bank.h"
#include "sound_dna/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
static SdProfile model,saved,second;
static SaBank bank,old_bank;
static SdVoice raw;
/* One component: rho +288*(mean4+basis4+rho1+root16)=7201 tokens.
   Independent serialized fixtures deliberately corrupt even inaudible orders. */
static int write_model(const char *path,const char *header,unsigned tokens,int bad,const char *value,int tail) {
    unsigned i;FILE *f=fopen(path,"wb");if(!f)return 0;
    fprintf(f,"%s\n",header);
    for(i=0;i<tokens;++i)fprintf(f,"%s ",(int)i==bad?value:"0");
    if(tail)fputs("unconsumed\n",f);
    return !ferror(f)&&fclose(f)==0;
}
int main(int argc,char **argv) {
    const SdProfile *p[2]={&model,&second};unsigned i;
    const char *valid="VSL_SOUND_DNA 1 48000 1024 256 288 1 90";
    const char *invalid[]={
        "VSL_SOUND_DNA 2 48000 1024 256 288 1 90",
        "WRONG 1 48000 1024 256 288 1 90",
        "VSL_SOUND_DNA 1 44100 1024 256 288 1 90",
        "VSL_SOUND_DNA 1 48000 2048 256 288 1 90",
        "VSL_SOUND_DNA 1 48000 1024 128 288 1 90",
        "VSL_SOUND_DNA 1 48000 1024 256 0 1 90",
        "VSL_SOUND_DNA 1 48000 1024 256 321 1 90",
        "VSL_SOUND_DNA 1 48000 1024 256 288 17 90",
        "VSL_SOUND_DNA 1 48000 1024 256 288 1 4.99999",
        "VSL_SOUND_DNA 1 48000 1024 256 288 1 1000.00001",
        "VSL_SOUND_DNA 1 48000 1024 256 288 1 nan",
        "VSL_SOUND_DNA 1 48000 1024 256 288 1 inf"};
    const int at[]={0,1,5,9,10,7176,7200};
    const char *bad[]={".950001","4.00001","nan","-.950001","inf","-4.00001","4.00001"};
    char header[128];double limit=21600/(288*1.1);
    CHECK(argc==2);
    CHECK(write_model(argv[1],valid,7201,-1,"",0));
    memset(&model,0x51,sizeof model);saved=model;
    CHECK(!sd_profile_load(argv[1],&model)&&!memcmp(&model,&saved,sizeof model));
    CHECK(sd_profile_load_bandlimited(argv[1],&model)&&model.base_hz==90&&model.harmonics==288);
    CHECK(!sd_voice_init(&raw,&model,23117,1,1,1));
    CHECK(!sa_bank_init(&bank,p,1,0));
    CHECK(sa_bank_init_bandlimited(&bank,p,1,0));old_bank=bank;saved=model;
    for(i=0;i<sizeof invalid/sizeof invalid[0];++i) {
        CHECK(write_model(argv[1],invalid[i],7201,-1,"",0));
        CHECK(!sd_profile_load_bandlimited(argv[1],&model)&&!memcmp(&model,&saved,sizeof model));
    }
    for(i=0;i<sizeof at/sizeof at[0];++i) {
        CHECK(write_model(argv[1],valid,7201,at[i],bad[i],0));
        CHECK(!sd_profile_load_bandlimited(argv[1],&model)&&!memcmp(&model,&saved,sizeof model));
    }
    CHECK(write_model(argv[1],valid,7200,-1,"",0));
    CHECK(!sd_profile_load_bandlimited(argv[1],&model)&&!memcmp(&model,&saved,sizeof model));
    CHECK(write_model(argv[1],valid,7201,-1,"",1));
    CHECK(!sd_profile_load_bandlimited(argv[1],&model)&&!memcmp(&model,&saved,sizeof model));
    CHECK(!sd_profile_load_bandlimited(NULL,&model)&&!sd_profile_load_bandlimited(argv[1],NULL));
    for(i=0;i<2;++i) {
        double root=limit+(i?1e-6:-1e-6);
        snprintf(header,sizeof header,"VSL_SOUND_DNA 1 48000 1024 256 288 1 %.17g",root);
        CHECK(write_model(argv[1],header,7201,-1,"",0));
        CHECK(sd_profile_load(argv[1],&model)==!i);
        CHECK(sd_profile_load_bandlimited(argv[1],&model));
        CHECK(sd_voice_init(&raw,&model,1,1,1,1)==!i);
        CHECK(sa_bank_init(&bank,p,1,0)==!i);
    }
    for(i=0;i<2;++i) {
        snprintf(header,sizeof header,"VSL_SOUND_DNA 1 48000 1024 256 288 1 %u",i?1000:5);
        CHECK(write_model(argv[1],header,7201,-1,"",0));
        CHECK(sd_profile_load_bandlimited(argv[1],&model));
        CHECK(sa_bank_init_bandlimited(&bank,p,1,0));
    }
    bd_model(&model,80,288,1);bd_model(&second,100,288,1);
    CHECK(sa_bank_init_bandlimited(&bank,p,2,8));old_bank=bank;
#define REJECT(x) do {CHECK(!(x));CHECK(!memcmp(&bank,&old_bank,sizeof bank));} while(0)
    REJECT(sa_bank_init(&bank,p,2,8));
    REJECT(sa_bank_init_bandlimited(&bank,p,0,0));
    REJECT(sa_bank_init_bandlimited(&bank,p,9,0));
    REJECT(sa_bank_init_bandlimited(&bank,p,2,33));
    REJECT(sa_bank_init_bandlimited(&bank,NULL,2,0));
    CHECK(!sa_bank_init_bandlimited(NULL,p,2,0));
    second.base_hz=80;REJECT(sa_bank_init_bandlimited(&bank,p,2,0));second.base_hz=100;
    second.harmonics=287;REJECT(sa_bank_init_bandlimited(&bank,p,2,0));second.harmonics=288;
    second.base_hz=1001;REJECT(sa_bank_init_bandlimited(&bank,p,2,0));second.base_hz=100;
    second.harmonic[287].mean[0]=NAN;REJECT(sa_bank_init_bandlimited(&bank,p,2,0));second.harmonic[287].mean[0]=0;
    second.harmonic[287].basis[1][3]=4.01;REJECT(sa_bank_init_bandlimited(&bank,p,2,0));second.harmonic[287].basis[1][3]=0;
    second.harmonic[287].rho=1;REJECT(sa_bank_init_bandlimited(&bank,p,2,0));second.harmonic[287].rho=0;
    second.harmonic[287].root[3][3]=INFINITY;REJECT(sa_bank_init_bandlimited(&bank,p,2,0));second.harmonic[287].root[3][3]=0;
    second.rho[1]=-.96;REJECT(sa_bank_init_bandlimited(&bank,p,2,0));second.rho[1]=0;
    CHECK(sa_bank_init_bandlimited(&bank,p,2,8));
    puts("PASS explicit opt-in/full coefficient validation/legacy boundary/transactionality");return 0;
}

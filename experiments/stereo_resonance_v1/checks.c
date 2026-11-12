#include "stereo_resonance/voice.h"
#include "stereo_resonance_io/profile.h"
#include "io/file.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static RvsProfile p,snapshot,loaded;static RvsVoice a,b;
#define CHECK(x) do{if(!(x)){fprintf(stderr,"stereo resonance line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static int multichannel(void) {
    const double coef[3][2][2]={{{.23,.04},{-.06,-.18}},{{.08,-.02},{.03,.05}},{{-.04,.01},{.02,.03}}};
    RdtExcitation rng[2];double hist[3][2]={{0}},xh[2][2]={{0}},yh[2][2]={{0}};unsigned i,j,k,n;
    RvsBand *m=p.band;memset(&p,0,sizeof p);p.rate=48000;p.count=1;p.base_hz=35;
    m->order=3;m->low_hz=400;m->high_hz=800;m->gain=.8;memcpy(m->a,coef,sizeof coef);
    m->noise[0][0]=.3;m->noise[1][0]=.17;m->noise[1][1]=.2;
    for(i=0;i<6;++i)m->certificate[i][i]=1-.3*(i/2);
    m->post.sections=1;memcpy(m->post.sos[0],(double[6]){.4,-.1,.03,1,-.3,.08},6*sizeof(double));
    CHECK(rvs_profile_valid(&p)&&rvs_voice_init(&a,&p,619,1));
    for(i=0;i<2;++i)rdt_excitation_init(rng+i,619^(UINT64_C(0x9e3779b97f4a7c15)*(i+1)));
    for(n=0;n<4096;++n) {
        double z[2],x[2],out[2];for(i=0;i<2;++i)z[i]=rdt_excitation_next(rng+i);
        for(i=0;i<2;++i){x[i]=m->noise[i][0]*z[0]+m->noise[i][1]*z[1];
            for(j=0;j<3;++j)for(k=0;k<2;++k)x[i]+=coef[j][i][k]*hist[j][k];}
        CHECK(rvs_voice_tick(&a,out,NULL));
        for(i=0;i<2;++i){double y=.4*x[i]-.1*xh[0][i]+.03*xh[1][i]+.3*yh[0][i]-.08*yh[1][i];
            CHECK(fabs(out[i]-.8*y)<2e-15);xh[1][i]=xh[0][i];xh[0][i]=x[i];yh[1][i]=yh[0][i];yh[0][i]=y;}
        for(j=2;j>0;--j)for(i=0;i<2;++i)hist[j][i]=hist[j-1][i];
        for(i=0;i<2;++i)hist[0][i]=x[i];
    }
    m->a[2][0][0]=2;CHECK(!rvs_profile_valid(&p));m->a[2][0][0]=coef[2][0][0];
    p.warmup_frames=113;CHECK(rvs_voice_init(&a,&p,732,1));p.warmup_frames=0;CHECK(rvs_voice_init(&b,&p,732,1));
    for(i=0;i<113;++i){double out[2];CHECK(rvs_voice_tick(&b,out,NULL));}
    CHECK(!memcmp(a.history,b.history,sizeof a.history)&&!memcmp(a.excitation,b.excitation,sizeof a.excitation)&&
          !memcmp(a.post,b.post,sizeof a.post));
    return 0;
}
static int io_cases(const char *path) {
    unsigned i,j,k,c;FILE *f;RvsBand *m=p.band;
    snapshot=p;f=vsl_fopen(path,"wb");CHECK(f);
    fprintf(f,"VSL_STEREO_RESONANCE 1 %u %u %u %.17g\n",p.rate,p.count,p.warmup_frames,p.base_hz);
    fprintf(f,"%u %u %.17g %.17g %.17g\n",m->order,m->post.sections,m->low_hz,m->high_hz,m->gain);
    for(j=0;j<m->order;++j)for(k=0;k<2;++k)for(c=0;c<2;++c)fprintf(f,"%.17g ",m->a[j][k][c]);
    for(j=0;j<2;++j)for(k=0;k<2;++k)fprintf(f,"%.17g ",m->noise[j][k]);
    for(j=0;j<m->post.sections;++j)for(k=0;k<6;++k)fprintf(f,"%.17g ",m->post.sos[j][k]);
    for(j=0;j<2*m->order;++j)for(k=0;k<2*m->order;++k)fprintf(f,"%.17g ",m->certificate[j][k]);
    CHECK(fclose(f)==0&&rvs_profile_load(path,&loaded)&&!memcmp(&snapshot,&loaded,sizeof loaded));
    f=vsl_fopen(path,"ab");CHECK(f);fputs("trailing_token",f);CHECK(fclose(f)==0);
    CHECK(!rvs_profile_load(path,&loaded)&&!memcmp(&snapshot,&loaded,sizeof loaded));
    for(i=0;i<3;++i){f=vsl_fopen(path,"wb");CHECK(f);
        fputs(i==0?"VSL_STEREO_RESONANCE 1 48000 1 0 35\n3 1 400 800 1\n.1":
              i==1?"VSL_STEREO_RESONANCE 2 48000 1 0 35":
                   "VSL_STEREO_RESONANCE 1 48000 13 0 35",f);CHECK(fclose(f)==0);
        CHECK(!rvs_profile_load(path,&loaded)&&!memcmp(&snapshot,&loaded,sizeof loaded));}
    CHECK(remove(path)==0);return 0;
}
int main(int argc,char **argv) {
    RdtExcitation rng[2];double history[2]={0};unsigned i,j;RvsBand *m=p.band;
    p.rate=48000;p.count=1;p.base_hz=35;m->order=1;m->low_hz=400;m->high_hz=800;m->gain=.7;
    m->a[0][0][0]=.5;m->a[0][1][1]=-.4;m->noise[0][0]=.3;m->noise[1][0]=.2;m->noise[1][1]=.1;
    m->certificate[0][0]=m->certificate[1][1]=1;m->post.sections=1;m->post.sos[0][0]=m->post.sos[0][3]=1;
    CHECK(rvs_profile_valid(&p)&&rvs_voice_init(&a,&p,9127,1)&&rvs_voice_init(&b,&p,9127,0));
    for(i=0;i<2;++i)rdt_excitation_init(rng+i,9127^(UINT64_C(0x9e3779b97f4a7c15)*(i+1)));
    for(i=0;i<2000;++i){double out[2],muted[2],raw[2],z[2],expected[2];
        for(j=0;j<2;++j)z[j]=rdt_excitation_next(rng+j);
        expected[0]=.3*z[0]+.5*history[0];expected[1]=.2*z[0]+.1*z[1]-.4*history[1];
        CHECK(rvs_voice_tick(&a,out,NULL)&&rvs_voice_tick(&b,muted,raw));
        for(j=0;j<2;++j){CHECK(fabs(out[j]-.7*expected[j])<1e-14&&out[j]==raw[j]&&muted[j]==0);history[j]=expected[j];}
        CHECK(!memcmp(a.history,b.history,sizeof a.history)&&!memcmp(a.excitation,b.excitation,sizeof a.excitation));
    }
    CHECK(!rvs_voice_set(&a,NAN));CHECK(rvs_voice_set(&a,.2));
    for(i=0;i<100;++i){double old=a.amount,out[2];CHECK(rvs_voice_tick(&a,out,NULL)&&a.amount<=old&&a.amount>=.2);}
    m->a[0][0][0]=1.01;CHECK(!rvs_profile_valid(&p));m->a[0][0][0]=.5;
    m->certificate[0][0]=-1;CHECK(!rvs_profile_valid(&p));m->certificate[0][0]=1;
    m->certificate[0][1]=.1;CHECK(!rvs_profile_valid(&p));m->certificate[0][1]=0;
    m->noise[1][1]=0;CHECK(!rvs_profile_valid(&p));m->noise[1][1]=.1;
    m->post.sos[0][5]=1.01;CHECK(!rvs_profile_valid(&p));
    CHECK(multichannel()==0&&argc==2&&io_cases(argv[1])==0);
    puts("PASS: stereo multichannel/multilag/SOS recurrence, warmup, muted continuity, amount, Lyapunov and transactional IO");return 0;
}

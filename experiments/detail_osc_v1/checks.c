#include "stream.h"
#include <math.h>
#include <stdio.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"failed line%d: %s\n",__LINE__,#x);return 1;}}while(0)
int main(int argc,char **argv) {
    DoModel m={0};DePlayer a,b;double x[1024],y[1024],position;unsigned n,j;uint64_t frames=0;
    CHECK(argc==2&&do_model_load(argv[1],&m));
    CHECK(de_init(&a,&m,1,1,0)&&de_init(&b,&m,1,1,0));
    for(j=0;j<50;++j) {
        CHECK(de_process(&a,x,1024)==1024);
        CHECK(de_process(&b,y,257)==257&&de_process(&b,y+257,767)==767);
        for(n=0;n<1024;++n)CHECK(x[n]==y[n]&&isfinite(x[n]));
    }
    CHECK(!de_set(&a,NAN,1,0)&&!de_set(&a,1.11,1,0)&&!de_set(&a,1,-.1,0));
    position=a.position;CHECK(de_set(&a,1.1,.5,0));CHECK(a.position==position);
    CHECK(de_process(&a,x,1)==1&&a.pitch>1&&a.pitch<1.001&&a.gain<1&&a.gain>.99);
    CHECK(de_init(&a,&m,1,1,1));
    while(frames<m.frames+1024){n=de_process(&a,x,1024);CHECK(n==1024);frames+=n;}
    CHECK(a.loops==1&&a.position<2048);CHECK(de_set(&a,1,1,0));
    while((n=de_process(&a,x,1024))!=0)for(j=0;j<n;++j)CHECK(isfinite(x[j]));
    CHECK(a.position>=m.frames&&de_process(&a,x,1)==0);
    do_model_free(&m);puts("DetailOSC1 block, smoothing, invalid-input, loop and end checks pass");return 0;
}

#include "profile.h"
#include <math.h>
#include <string.h>
static int positive(double a[RVS_MAX_DIM][RVS_MAX_DIM],unsigned n) {
    unsigned i,j,k;double scale=0;
    for(i=0;i<n;++i)scale=fmax(scale,fabs(a[i][i]));
    if(!(scale>0)||!isfinite(scale))return 0;
    for(i=0;i<n;++i)for(j=0;j<=i;++j) {
        double value=a[i][j];for(k=0;k<j;++k)value-=a[i][k]*a[j][k];
        if(i==j){if(!isfinite(value)||value<=scale*1e-12)return 0;a[i][j]=sqrt(value);}
        else a[i][j]=value/a[j][j];
    }return 1;
}
static int stable(const RvsBand *b) {
    double f[RVS_MAX_DIM][RVS_MAX_DIM]={{0}},p[RVS_MAX_DIM][RVS_MAX_DIM],pf[RVS_MAX_DIM][RVS_MAX_DIM]={{0}};
    double q[RVS_MAX_DIM][RVS_MAX_DIM];unsigned n=2*b->order,i,j,k;
    for(i=0;i<2;++i)for(j=0;j<b->order;++j)for(k=0;k<2;++k)f[i][2*j+k]=b->a[j][i][k];
    for(i=2;i<n;++i)f[i][i-2]=1;
    for(i=0;i<n;++i)for(j=0;j<n;++j) {
        p[i][j]=b->certificate[i][j];
        if(!isfinite(p[i][j])||fabs(p[i][j]-b->certificate[j][i])>1e-12)return 0;
    }
    for(i=0;i<n;++i)for(j=0;j<n;++j)for(k=0;k<n;++k)pf[i][j]+=p[i][k]*f[k][j];
    for(i=0;i<n;++i)for(j=0;j<n;++j) {
        q[i][j]=p[i][j];for(k=0;k<n;++k)q[i][j]-=f[k][i]*pf[k][j];
    }
    return positive(p,n)&&positive(q,n);
}
int rvs_profile_valid(const RvsProfile *p) {
    unsigned i,j,k,c;
    if(!p||p->rate!=48000||!p->count||p->count>RVS_MAX_BANDS||p->warmup_frames>480000||
       !isfinite(p->base_hz)||p->base_hz<=0)return 0;
    for(i=0;i<p->count;++i) {
        const RvsBand *b=p->band+i;
        if(!b->order||b->order>RVS_MAX_ORDER||!isfinite(b->low_hz)||!isfinite(b->high_hz)||
           b->low_hz<100||b->high_hz<=b->low_hz||b->high_hz>16000||!isfinite(b->gain)||b->gain<0||
           !b->post.sections||b->post.sections>RDT_MAX_SOS)return 0;
        for(j=0;j<b->order;++j)for(k=0;k<2;++k)for(c=0;c<2;++c)if(!isfinite(b->a[j][k][c]))return 0;
        for(j=0;j<2;++j)for(k=0;k<2;++k)if(!isfinite(b->noise[j][k]))return 0;
        if(b->noise[0][0]<=0||b->noise[1][1]<=0||b->noise[0][1]!=0)return 0;
        for(j=0;j<b->post.sections;++j) {
            const double *s=b->post.sos[j];for(k=0;k<6;++k)if(!isfinite(s[k]))return 0;
            if(s[3]!=1||fabs(s[5])>=1||1+s[4]+s[5]<=0||1-s[4]+s[5]<=0)return 0;
        }
        if(!stable(b))return 0;
    }return 1;
}

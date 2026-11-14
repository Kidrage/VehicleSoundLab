#ifndef VSL_LOCAL_ATLAS_INPUT_H
#define VSL_LOCAL_ATLAS_INPUT_H
#include <ctype.h>
#include <stdio.h>
/* Bounded unsigned decimal token; scanf %u would accept signs and wrap values. */
static int la_unsigned(FILE *f,unsigned limit,unsigned *out) {
    unsigned value=0,digit;int c;
    do{c=fgetc(f);}while(c!=EOF&&isspace((unsigned char)c));
    if(c<'0'||c>'9')return 0;
    do{
        digit=(unsigned)(c-'0');
        if(digit>limit||value>(limit-digit)/10)return 0;
        value=value*10+digit;c=fgetc(f);
    }while(c>='0'&&c<='9');
    if(c!=EOF&&!isspace((unsigned char)c))return 0;
    if(c!=EOF)ungetc(c,f);
    *out=value;return 1;
}
#endif

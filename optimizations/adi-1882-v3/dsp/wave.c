#include "wave.h"
#include "wave_table.h"
float vsl_sine(float radians){
    float p=radians*651.8986469044033f;int i=(int)p;float u=p-i;
    if(u<0){--i;u+=1;}
    return wave_table[(unsigned)i&4095]+u*(wave_table[((unsigned)i+1)&4095]-wave_table[(unsigned)i&4095]);
}
float vsl_cosine(float radians){return vsl_sine(radians+1.57079632679489661923f);}

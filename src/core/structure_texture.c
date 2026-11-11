#include "structure_texture.h"
void vsl_character_structure_init(VslCharacterStructure *p,double rate) {
    const VslCharacterProfile *s=vsl_character_profile();int i;
    for(i=0;i<VSL_CHARACTER_STRUCTURE_MODES;++i)
        vsl_mode_init(&p->mode[i],s->structure[i].hz,s->structure[i].decay,rate);
}
void vsl_character_structure_advance(VslCharacterStructure *p) {
    int i;for(i=0;i<VSL_CHARACTER_STRUCTURE_MODES;++i)(void)vsl_mode_tick(&p->mode[i]);
}
void vsl_character_structure_strike(VslCharacterStructure *p,double gain,double shape,double elapsed) {
    const VslCharacterProfile *s=vsl_character_profile();int i;
    for(i=0;i<VSL_CHARACTER_STRUCTURE_MODES;++i)
        vsl_mode_strike(&p->mode[i],gain*s->structure[i].weight*(1+.12*shape),elapsed);
}
double vsl_character_structure_read(const VslCharacterStructure *p) {
    double x=0;int i;for(i=0;i<VSL_CHARACTER_STRUCTURE_MODES;++i)x+=p->mode[i].real;return x;
}

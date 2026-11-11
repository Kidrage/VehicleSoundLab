#ifndef VSL_DNA_SCENE_CHECKS_H
#define VSL_DNA_SCENE_CHECKS_H
#include "dna_scene/scene.h"
#include <stdio.h>
extern int failures;
#define CHECK(x, message) do { if (!(x)) { fprintf(stderr, "FAIL: %s (%s:%d)\n", message, __FILE__, __LINE__); ++failures; } } while (0)
void source_checks(const SdProfile *dna, const SdProfile *low);
void spatial_checks(const SdProfile *dna, const SdProfile *low);
DsSceneConfig test_config(const SdProfile *dna, const SdProfile *low);
DsSceneControl test_control(void);
#endif

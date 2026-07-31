#ifndef ORB_CORE_H
#define ORB_CORE_H

typedef struct SkiffSample {
    double x;
    double y;
    double vx;
    double vy;
    int on;
    int grace;
    int stash;
    int hops;
    double apex;
} SkiffSample;

SkiffSample skiff_sample_init(double x, double y);
void skiff_drift(SkiffSample *s);
void skiff_arm(SkiffSample *s);
void skiff_kick(SkiffSample *s);
int skiff_arm_g(int a, int b, int c);

#endif

#include "astrotime.h"
#include <math.h>

double astro_wrap_degrees(double x) {
    double r = fmod(x, 360.0);
    if (r < 0) r += 360.0;
    if (r >= 360.0) r -= 360.0;
    return r;
}

double astro_hermite(double y0, double m0, double y1, double m1, double t, double span) {
    double h00 = 2*t*t*t - 3*t*t + 1;
    double h10 = t*t*t - 2*t*t + t;
    double h01 = -2*t*t*t + 3*t*t;
    double h11 = t*t*t - t*t;
    return h00*y0 + h10*span*m0 + h01*y1 + h11*span*m1;
}

double astro_phase_hermite(double d0, double s0, double d1, double s1, double t, double span) {
    double delta = fmod(d1 - d0 + 540.0, 360.0) - 180.0;
    double unwrapped = d0 + delta;
    return astro_wrap_degrees(astro_hermite(d0, s0, unwrapped, s1, t, span));
}

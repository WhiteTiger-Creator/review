#include "cvss.h"

#include <math.h>
#include <string.h>

#include "common.h"

static double roundup(double x)
{
    long long i = llround(x * 100000.0);
    if (i % 10000 == 0)
        return (double)i / 100000.0;
    return (double)(i / 10000 + 1) / 10.0;
}

static double weight_cia(char c, const char *vector)
{
    switch (c) {
    case 'H':
        return 0.56;
    case 'L':
        return 0.22;
    case 'N':
        return 0.0;
    default:
        die("bad C/I/A value in vector %s", vector);
        return 0.0;
    }
}

double cvss31_base(const char *vector)
{
    char av = 0, ac = 0, pr = 0, ui = 0, sc = 0, mc = 0, mi = 0, ma = 0;
    const char *p;
    double wav, wac, wpr, wui, c, i, a;
    double iss, impact, expl;
    int changed;

    if (strncmp(vector, "CVSS:3.1/", 9) != 0)
        die("unsupported CVSS vector %s", vector);
    for (p = vector + 9; *p;) {
        const char *sep = strchr(p, '/');
        size_t seg = sep ? (size_t)(sep - p) : strlen(p);
        if (seg >= 4 && p[2] == ':') {
            if (p[0] == 'A' && p[1] == 'V')
                av = p[3];
            else if (p[0] == 'A' && p[1] == 'C')
                ac = p[3];
            else if (p[0] == 'P' && p[1] == 'R')
                pr = p[3];
            else if (p[0] == 'U' && p[1] == 'I')
                ui = p[3];
        } else if (seg >= 3 && p[1] == ':') {
            if (p[0] == 'S')
                sc = p[2];
            else if (p[0] == 'C')
                mc = p[2];
            else if (p[0] == 'I')
                mi = p[2];
            else if (p[0] == 'A')
                ma = p[2];
        }
        if (!sep)
            break;
        p = sep + 1;
    }
    if (!av || !ac || !pr || !ui || !sc || !mc || !mi || !ma)
        die("incomplete CVSS vector %s", vector);
    changed = (sc == 'C');

    switch (av) {
    case 'N': wav = 0.85; break;
    case 'A': wav = 0.62; break;
    case 'L': wav = 0.55; break;
    case 'P': wav = 0.2; break;
    default: die("bad AV in %s", vector); return 0.0;
    }
    switch (ac) {
    case 'L': wac = 0.77; break;
    case 'H': wac = 0.44; break;
    default: die("bad AC in %s", vector); return 0.0;
    }
    switch (pr) {
    case 'N': wpr = 0.85; break;
    case 'L': wpr = changed ? 0.68 : 0.62; break;
    case 'H': wpr = changed ? 0.5 : 0.27; break;
    default: die("bad PR in %s", vector); return 0.0;
    }
    switch (ui) {
    case 'N': wui = 0.85; break;
    case 'R': wui = 0.62; break;
    default: die("bad UI in %s", vector); return 0.0;
    }
    c = weight_cia(mc, vector);
    i = weight_cia(mi, vector);
    a = weight_cia(ma, vector);

    iss = 1.0 - (1.0 - c) * (1.0 - i) * (1.0 - a);
    if (changed)
        impact = 7.52 * (iss - 0.029) - 3.25 * pow(iss - 0.02, 15.0);
    else
        impact = 6.42 * iss;
    expl = 8.22 * wav * wac * wpr * wui;
    if (impact <= 0.0)
        return 0.0;
    if (changed)
        return roundup(fmin(1.08 * (impact + expl), 10.0));
    return roundup(fmin(impact + expl, 10.0));
}

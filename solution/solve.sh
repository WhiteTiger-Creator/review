#!/usr/bin/env bash
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$HERE"

/usr/bin/patch -p1 -d /app < ./oracle_e.patch
/usr/bin/patch -p1 -d /app < ./oracle_a.patch
/usr/bin/patch -p1 -d /app < ./oracle_b.patch
/usr/bin/patch -p1 -d /app < ./oracle_c.patch
/usr/bin/patch -p1 -d /app < ./oracle_d.patch
/usr/bin/patch -p1 -d /app < ./oracle_f.patch
/usr/bin/patch -p1 -d /app < ./oracle_g.patch
/usr/bin/patch -p1 -d /app < ./oracle_h.patch
/usr/bin/patch -p1 -d /app < ./oracle_i.patch
/usr/bin/patch -p1 -d /app < ./oracle_j.patch
/usr/bin/patch -p1 -d /app < ./oracle_k.patch
/usr/bin/patch -p1 -d /app < ./oracle_l.patch
/usr/bin/patch -p1 -d /app < ./oracle_m.patch

mkdir -p /app/output
/usr/bin/mvn -q -f /app/pom.xml -DskipTests package
chmod +x /app/bin/uxr
/app/bin/uxr

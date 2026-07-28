#!/bin/bash
# Reference solution: land the range sieve, the search course and the artifact
# scribe, teach the command table the new subcommand, rebuild the module and
# publish every project. Fully offline.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

mkdir -p /app/internal/sieve /app/internal/course /app/internal/scribe

patch -p1 -d /app < files/01-sieve-bounds.patch
patch -p1 -d /app < files/02-sieve-admit.patch
patch -p1 -d /app < files/03-course-frame.patch
patch -p1 -d /app < files/04-course-sweep.patch
patch -p1 -d /app < files/05-scribe-shape.patch
patch -p1 -d /app < files/06-scribe-mint.patch
patch -p1 -d /app < files/07-console-subrun.patch
patch -p1 -d /app < files/08-console-dispatch.patch

cd /app
make clean
make all

mkdir -p /app/out
/app/bin/slate resolve --all

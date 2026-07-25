#!/usr/bin/env bash
set -euo pipefail
cp /solution/lyap_solution.c /app/lyap.c
cc -O2 -std=c11 -o /app/lyap /app/lyap.c -lm
/app/lyap /app/data /app/oracle_out.txt
head -n 1 /app/oracle_out.txt

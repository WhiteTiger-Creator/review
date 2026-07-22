#!/bin/bash
set -euo pipefail

cd /app
rm -rf /app/out
rm -rf /app/bin
mkdir -p /app/bin
g++ -std=c++17 -O2 -Wall -Wextra -pedantic -I/app/include \
  -o /app/bin/apnea_hmm /app/src/apnea_hmm.cpp
/app/bin/apnea_hmm \
  --train /app/data/train \
  --adapt /app/data/adaptation \
  --validation /app/data/validation \
  --infer /app/data/inference \
  --out-dir /app/out

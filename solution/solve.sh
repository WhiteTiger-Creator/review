#!/bin/bash
set -euo pipefail

cp /solution/oracle_invert.awk /app/src/invert.awk
/app/bin/soilfit /app/data/soil.sqlite

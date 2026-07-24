#!/bin/bash
set -euo pipefail
cp /solution/Program.cs /app/task_file/src/Program.cs
make -C /app/task_file sphere-flux

#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p /app/outputs
cp "$DIR/analysis.R" /app/analysis.R
printf '%s\n' '#!/bin/bash' 'cd /app' 'Rscript /app/analysis.R' > /app/run.sh
chmod 0755 /app/run.sh
cd /app
bash /app/run.sh

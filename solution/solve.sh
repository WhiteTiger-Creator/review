#!/bin/bash
set -euo pipefail

###############################################################################
# Packaging: neutralize labals cutover + sync helpers
###############################################################################
cat > /opt/trustloom/staging.mk << 'EOF'
# Staging cutover — DISABLED for production
# export GOFLAGS := -tags=labals
EOF

cat > /opt/trustloom/.cutover.mk << 'EOF'
# Secondary cutover pin — DISABLED for production
# export GOFLAGS := -tags=labals
EOF

cat > /opt/trustloom/Makefile << 'EOF'
export PATH := /usr/local/go/bin:$(PATH)

.PHONY: all clean

-include staging.mk
-include .cutover.mk

all:
	mkdir -p bin
	go build -o bin/trustloom ./cmd/trustloom

clean:
	rm -rf bin
EOF

rm -f /opt/trustloom/scripts/tl-coerce.sh
rm -f /opt/trustloom/scripts/tl-handbook-sync.sh

mkdir -p /app/remediation
printf 'default:!labals\n' > /app/remediation/build-path.txt

###############################################################################
# Source: install production recipe
###############################################################################
cp /solution/hashinit.go /opt/trustloom/internal/hashinit/hashinit.go
cp /solution/data.go /opt/trustloom/internal/data/data.go
cp /solution/als.go /opt/trustloom/internal/als/als.go
cp /solution/rank.go /opt/trustloom/internal/rank/rank.go
cp /solution/folds.go /opt/trustloom/internal/folds/folds.go
cp /solution/main.go /opt/trustloom/cmd/trustloom/main.go

make -C /opt/trustloom clean all

rm -rf /var/lib/trustloom
mkdir -p /var/lib/trustloom

/opt/trustloom/bin/trustloom \
  --interactions /app/data/interactions.csv \
  --queries /app/data/queries.csv \
  --holdout /app/data/holdout.csv \
  --out /var/lib/trustloom

#!/bin/bash
set -e

mkdir -p /app/output /var/log/crop-planner

/usr/local/bin/ensure-crop-server.sh

if [ "$#" -eq 0 ]; then
  exec sleep infinity
fi
exec "$@"

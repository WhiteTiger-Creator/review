#!/usr/bin/env bash
# Returns 0 when the server is accepting requests, 1 otherwise.
curl -sf http://localhost:${PORT:-8080}/stats > /dev/null 2>&1

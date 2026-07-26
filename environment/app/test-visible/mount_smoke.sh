#!/usr/bin/env bash
set -euo pipefail
/app/bin/inspect-mount-resolution --bundle /app/data/oci/archival --destination /etc/ssl/certs/harborseal-ca.pem >/dev/null

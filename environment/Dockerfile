FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

LABEL org.opencontainers.image.source="terminus/qr-model2-segment-interleave-mask-tournament"

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    bash \
    asciinema \
    ca-certificates \
    cmake \
    findutils \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
    zbar-tools \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

ENV PATH="/opt/verifier-venv/bin:/opt/verifier-scripts:${PATH}"

COPY app/ /app/
WORKDIR /app
RUN mkdir -p /app/bin /app/state /app/output/labels /app/build \
 && cmake -S /app -B /app/build -DCMAKE_BUILD_TYPE=Release \
 && cmake --build /app/build --target qr-composer \
 && install -m 0755 /app/build/qr-composer /app/bin/qr-composer

RUN mkdir -p /opt/verifier-scripts \
 && printf '%s\n' '#!/bin/bash' 'set -euo pipefail' \
    'export PATH="/usr/local/bin:/usr/bin:/bin:${PATH}"' \
    'cd /app' \
    'cmake --build /app/build --target qr-composer' \
    'install -m 0755 /app/build/qr-composer /app/bin/qr-composer' \
    > /opt/verifier-scripts/rebuild-qr-composer \
 && chmod +x /opt/verifier-scripts/rebuild-qr-composer

WORKDIR /app

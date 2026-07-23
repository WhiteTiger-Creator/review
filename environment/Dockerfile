# Canonical Terminal-Bench Node.js base image (exact platform-sanctioned
# reference, digest-pinned). Node 22 provides the TypeScript toolchain the
# task builds with at image build time and rebuilds at runtime.
FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-venv=3.11.2-1+b1 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        patch=2.7.6-7 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

ENV PATH="/opt/verifier-venv/bin:${PATH}"

WORKDIR /app

COPY package.json package-lock.json tsconfig.json ./
COPY scripts ./scripts
COPY m3 ./m3
COPY p8 ./p8
COPY data ./data
COPY docs ./docs

RUN npm config set fetch-retries 5 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm ci --no-audit --no-fund \
    && npm run build \
    && rm -rf /root/.npm /tmp/*

# TrustLoom TL-ALS-CONF-1: implicit-feedback collaborative filtering (ALS).
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pip \
        make \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages --require-hashes --no-deps -r /tmp/requirements.txt

COPY app/ /app/
COPY opt/trustloom/ /opt/trustloom/

RUN mkdir -p /var/lib/trustloom /opt/trustloom/bin \
    && find /opt/trustloom /app -type f \( -name '*.go' -o -name '*.mod' -o -name 'Makefile' -o -name '*.mk' -o -name '*.txt' -o -name '*.md' -o -name '*.csv' -o -name '*.sh' \) -exec sed -i 's/\r$//' {} + \
    && chmod +x /opt/trustloom/scripts/*.sh 2>/dev/null || true

LABEL org.opencontainers.image.source="https://github.com/snorkel-ai/trustloom-als-conf"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.revision="trustloom-als-conf-1"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.created="2026-07-23T00:00:00Z"

WORKDIR /app

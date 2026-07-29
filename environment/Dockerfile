# Lua has no canonical image family, so the canonical Debian runtime is used and the distro Lua toolchain is installed below.
FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

LABEL org.opencontainers.image.source="local/contamination-forensics-lua" \
      org.opencontainers.image.version="1.0" \
      org.opencontainers.image.licenses="MIT"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        lua-cjson \
        lua-socket \
        lua5.4 \
        python-is-python3 \
        python3-pip \
        sqlite3 \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /opt/verifier/requirements.lock

RUN python -m pip install --no-cache-dir --break-system-packages \
    --require-hashes \
    --no-deps \
    -r /opt/verifier/requirements.lock

WORKDIR /app

COPY Makefile /app/Makefile
COPY --chmod=0755 bin/memscope /app/bin/memscope
COPY src/ /app/src/
COPY config/ /app/config/
COPY data/ /app/data/
COPY mock_model/ /app/mock_model/
COPY docs/ /app/docs/

RUN mkdir -p /app/output

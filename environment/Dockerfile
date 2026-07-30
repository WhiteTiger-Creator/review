# syntax=docker/dockerfile:1
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema \
    build-essential \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
 && rm -rf /var/lib/apt/lists/*

COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements-verifier.txt \
 && rm -f /tmp/requirements-verifier.txt

WORKDIR /app

COPY Cargo.toml ./
COPY lib/ ./lib/
COPY tools/ ./tools/
COPY scripts/ ./scripts/
COPY docs/ ./docs/
COPY fixtures/ ./fixtures/

RUN chmod +x /app/scripts/build.sh \
 && /app/scripts/build.sh \
 && mkdir -p /app/output /app/state /app/bin

ENV PATH="/opt/verifier-venv/bin:/app/bin:/usr/local/cargo/bin:${PATH}"
ENV CARGO_TARGET_DIR=/app/target
ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup

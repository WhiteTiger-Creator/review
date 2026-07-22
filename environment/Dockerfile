FROM --platform=linux/amd64 public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

LABEL org.opencontainers.image.licenses="MIT"

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
 && rm -f /tmp/requirements.lock

ENV PATH="/opt/verifier-venv/bin:/app/bin:/usr/local/cargo/bin:${PATH}"

WORKDIR /app
COPY Cargo.toml Cargo.lock /app/
COPY src/ /app/src/
COPY docs/ /app/docs/
COPY fixtures/ /app/fixtures/

RUN cargo build --release --locked \
 && mkdir -p /app/bin /app/state /app/output \
 && cp /app/target/release/fmctl /app/bin/fmctl

WORKDIR /app

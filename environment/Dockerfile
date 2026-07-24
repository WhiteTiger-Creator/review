FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        patch \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

ENV PATH=/app/bin:/opt/verifier-venv/bin:/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV CARGO_TARGET_DIR=/app/target

WORKDIR /app

COPY Cargo.toml Cargo.lock rust-toolchain.toml /app/
COPY src/ /app/src/
COPY docs/ /app/docs/
COPY data/ /app/data/

RUN mkdir -p /app/out /app/state /app/bin /opt/verifier-fixtures \
    && cargo build --release --locked \
    && cp /app/target/release/trustadmit /app/bin/trustadmit

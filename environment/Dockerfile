# Multi-stage host build for Go control plane + Rust custody/fence helpers.
# Justification: golang bookworm final stage is the canonical Go runtime base and
# also hosts the Rust toolchain copy required to rebuild helpers offline.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust-base

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS toolchain

COPY --from=rust-base /usr/local/cargo /usr/local/cargo
COPY --from=rust-base /usr/local/rustup /usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    PATH=/usr/local/cargo/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    GOPATH=/go

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
        asciinema \
        build-essential \
        pkg-config \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app/environment
COPY . /app/environment

# Populate module/crate caches inside the image (not under solver-edited paths).
RUN go mod download \
    && cargo fetch --manifest-path /app/environment/Cargo.toml \
    && chmod +x /app/environment/scripts/build.sh \
    && /app/environment/scripts/build.sh

WORKDIR /app

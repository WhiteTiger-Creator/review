# Builder stages use canonical Rust and Go images; runtime is canonical python slim-bookworm.
# The agent edits the Rust kernel and Go driver and rebuilds inside the runtime
# container, so build-essential and the Rust/Go toolchains stay in the final image
# by design (check_no_build_tools_in_runtime warns here intentionally).
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust-build
WORKDIR /build
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
COPY orb-rs/Cargo.toml orb-rs/Cargo.lock ./
COPY orb-rs/src ./src
RUN cargo build --release --locked

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS go-build
WORKDIR /build
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential=12.9 \
    && rm -rf /var/lib/apt/lists/*
COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal
COPY include ./include
COPY orb-rs ./orb-rs
COPY --from=rust-build /build/target/release/liborb_core.a ./orb-rs/target/release/liborb_core.a
RUN GOFLAGS=-mod=mod CGO_ENABLED=1 go build -trimpath -buildvcs=false -o /out/skiff ./cmd/skiff

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/* \
    && command -v tmux \
    && command -v asciinema \
    && tmux -V \
    && asciinema --version \
    && python3 -c "import locale; locale.setlocale(locale.LC_ALL, ''); cs = locale.nl_langinfo(locale.CODESET); print('codeset', cs); assert cs.lower() in ('utf-8', 'utf8'), cs"
COPY verifier-requirements.txt /tmp/verifier-requirements.txt
# Verifier deps: pytest==8.4.1 pytest-json-ctrf==0.3.5
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/verifier-requirements.txt
RUN ln -sf "$(command -v python3)" /usr/local/bin/python && rm -f /tmp/verifier-requirements.txt
COPY --from=rust-build /usr/local/cargo /usr/local/cargo
COPY --from=rust-build /usr/local/rustup /usr/local/rustup
COPY --from=go-build /usr/local/go /usr/local/go
ENV PATH="/usr/local/cargo/bin:/usr/local/go/bin:${PATH}"
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && go version && cargo --version
ENV GOPROXY=off
ENV GOFLAGS=-mod=mod
ENV CGO_ENABLED=1
COPY go.mod /app/
COPY cmd /app/cmd
COPY internal /app/internal
COPY include /app/include
COPY orb-rs /app/orb-rs
COPY data /app/data
COPY docs /app/docs
COPY schemas /app/schemas
COPY scripts /app/scripts
COPY ops /app/ops
COPY harness /app/harness
COPY ci /app/ci
COPY README.md /app/README.md
COPY --from=rust-build /build/target/release/liborb_core.a /app/orb-rs/target/release/liborb_core.a
COPY --from=go-build /out/skiff /app/bin/skiff
RUN chmod +x /app/scripts/*.sh /app/ci/*.sh
LABEL org.opencontainers.image.title="skiff-hop-lab" \
      org.opencontainers.image.description="Skiff hop lab: Rust body step linked into a Go level driver." \
      org.opencontainers.image.version="1.0.0"
WORKDIR /app

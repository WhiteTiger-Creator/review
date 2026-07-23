FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV CARGO_NET_OFFLINE=true
ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV PATH=/usr/local/cargo/bin:$PATH

# The base image ships cargo/rustc as rustup proxy shims on a PATH set by the
# base image's ENV. Some agent harnesses launch a shell that does not inherit
# that ENV, leaving `cargo` unreachable and the build failing silently. Symlink
# the real toolchain binaries into /usr/local/bin (always on PATH) so the build
# works from a bare shell.
RUN set -eux; \
    real_cargo="$(find /usr/local/rustup/toolchains -maxdepth 3 -type f -name cargo | head -n1)"; \
    real_rustc="$(find /usr/local/rustup/toolchains -maxdepth 3 -type f -name rustc | head -n1)"; \
    ln -sf "$real_cargo" /usr/local/bin/cargo; \
    ln -sf "$real_rustc" /usr/local/bin/rustc; \
    /usr/local/bin/cargo --version; \
    /usr/local/bin/rustc --version

RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pip \
        make \
    && pip3 install --no-cache-dir --break-system-packages pytest==8.3.4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY src/ /app/src/
COPY docs/ /app/docs/
COPY data/ /app/data/
COPY Cargo.toml /app/Cargo.toml
COPY Makefile /app/Makefile

RUN cargo build --release --offline

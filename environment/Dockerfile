FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rsbuilder

ENV PATH="/usr/local/cargo/bin:${PATH}"

WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY core/Cargo.toml core/
COPY vfy/Cargo.toml vfy/
COPY skim/Cargo.toml skim/
# Stub sources so dependency fetch is not busted by real source edits.
RUN mkdir -p core/src vfy/src skim/src \
    && printf '#![allow(dead_code)]\n' > core/src/lib.rs \
    && printf 'fn main() {}\n' > vfy/src/main.rs \
    && printf 'fn main() {}\n' > skim/src/main.rs \
    && cargo fetch --locked
COPY core/src/ core/src/
COPY vfy/src/ vfy/src/
COPY skim/src/ skim/src/
RUN cargo build -p trusteval -p skim --release --locked

FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.licenses="MIT"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        bash \
        ca-certificates=20230311+deb12u1 \
        python-is-python3 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

ENV TERM=xterm-256color \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH="/usr/local/cargo/bin:/app/bin:${PATH}" \
    CARGO_NET_OFFLINE=true

RUN tmux -V \
    && asciinema --version \
    && tmux new-session -d -s _smoke \
    && tmux has-session -t _smoke \
    && tmux kill-session -t _smoke

COPY requirements.txt /tmp/requirements.txt
# Installs pytest==8.4.1 and pytest-json-ctrf==0.3.5 with hash-locked transitive deps.
RUN python3 -m pip install --no-cache-dir --break-system-packages --require-hashes \
    -r /tmp/requirements.txt
RUN rm -f /tmp/requirements.txt

WORKDIR /app

COPY --from=rsbuilder /usr/local/cargo /usr/local/cargo
COPY --from=rsbuilder /usr/local/rustup /usr/local/rustup
COPY --from=rsbuilder /build/target /app/target
COPY --from=rsbuilder --chmod=755 /build/target/release/trusteval /app/bin/trusteval
COPY --from=rsbuilder --chmod=755 /build/target/release/jarcheck /app/bin/jarcheck

# Login shells reset PATH and drop /usr/local/cargo/bin — keep cargo on the default PATH.
RUN ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && ln -sf /usr/local/cargo/bin/rustdoc /usr/local/bin/rustdoc

COPY Cargo.toml Cargo.lock /app/
COPY core/ /app/core/
COPY vfy/ /app/vfy/
COPY skim/ /app/skim/
COPY config/ /app/config/
COPY data/ /app/data/
COPY ops/ /app/ops/

RUN chmod +x /app/ops/run_mesh.sh \
    && mkdir -p /output /logs/verifier

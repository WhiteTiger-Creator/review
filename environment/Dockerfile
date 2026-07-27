FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

# Canonical Terminal-Bench Rust runtime; digest-pinned.

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    asciinema \
    python3 \
    python3-pip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.in /tmp/requirements.in
COPY requirements.lock /tmp/requirements.lock

RUN pip3 install --no-cache-dir --break-system-packages \
    --require-hashes --no-deps \
    -r /tmp/requirements.lock \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && rm -f /tmp/requirements.in /tmp/requirements.lock

ENV CARGO_HOME="/usr/local/cargo"
ENV RUSTUP_HOME="/usr/local/rustup"
ENV PATH="/usr/local/cargo/bin:/usr/local/rustup/bin:/root/.cargo/bin:/usr/local/bin:/usr/bin:/bin"

COPY app /app
COPY source_snapshots /app/source_snapshots

WORKDIR /app

RUN mkdir -p /app/output \
    && chmod 0777 /app/output

CMD ["sleep", "infinity"]

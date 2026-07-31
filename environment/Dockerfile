FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36
# cargo lives on PATH via the base image; link it into /usr/local/bin as well so
# it is reachable from shells that rebuild their own PATH
RUN ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
 && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip make tmux asciinema && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --break-system-packages --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock
COPY Cargo.toml /app/Cargo.toml
COPY src/ /app/src/
COPY docs/ /app/docs/
COPY example/ /app/example/
RUN cargo build --release

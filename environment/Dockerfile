# Canonical Terminal-Bench Rust runtime (docs/PLATFORM_AUTO_EVAL.md).
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    sqlite3=3.40.1-2+deb12u2 \
    patch=2.7.6-7 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    libssl3=3.0.20-1~deb12u2 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        pytest-randomly==3.16.0

RUN ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc

ENV PATH=/opt/verifier/bin:/usr/local/cargo/bin:/usr/local/bin:${PATH}
ENV CARGO_TARGET_DIR=/tmp/wf-target
RUN printf '%s\n' \
    'export PATH=/opt/verifier/bin:/usr/local/cargo/bin:/usr/local/bin:$PATH' \
    'export CARGO_TARGET_DIR=/tmp/wf-target' \
    > /etc/profile.d/wf-path.sh

RUN mkdir -p /app/output /logs/verifier

COPY . /app/environment

WORKDIR /app/environment
RUN chmod +x exec/k_run.sh exec/parts/*.sh scripts/build.sh \
    && ./scripts/build.sh \
    && cp /tmp/wf-target/release/wf_a /usr/local/bin/wf_a \
    && cp /tmp/wf-target/release/wf_b /usr/local/bin/wf_b \
    && cp /tmp/wf-target/release/wf_c /usr/local/bin/wf_c

WORKDIR /app

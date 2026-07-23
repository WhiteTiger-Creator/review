# Builder: sanctioned Rust canonical image (toolchain + registry fetch).
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust-builder

WORKDIR /build
ENV CARGO_TARGET_DIR=/build/target \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY Cargo.toml Cargo.lock ./
COPY w7x w7x
COPY p3n p3n
COPY k9m k9m
COPY v4q v4q
COPY probe probe
COPY native native

RUN cargo fetch --locked \
    && cargo build -p probe --locked

# Final runtime: sanctioned Python canonical base + Rust toolchain for offline rebuilds.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

LABEL org.opencontainers.image.source="local/tasks/rust-backend-layout-matrix" \
      org.opencontainers.image.revision="local" \
      org.opencontainers.image.created="2026-07-23T00:00:00Z" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.licenses="NOASSERTION"

WORKDIR /app

# Harbor agent sessions require tmux + asciinema. Missing either causes
# infrastructure crashes (verifier_did_not_run / GPT runs with no reward).
# Debian asciinema shebang is #!/usr/bin/python3 — install apt python3 so
# that path exists on the official slim image (which only ships
# /usr/local/bin/python3 by default). Session tools stay unpinned so apt
# mirrors that drift still resolve; build packages stay pinned.
ENV DEBIAN_FRONTEND=noninteractive \
    TERM=xterm-256color \
    TMPDIR=/tmp \
    TMUX_TMPDIR=/tmp

# One apt transaction: session tools first, then build/verifier deps.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        procps \
        psmisc \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1 \
        python3 \
        python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/output /tmp /var/tmp \
    && chmod 1777 /tmp /var/tmp \
    && command -v tmux >/dev/null \
    && command -v asciinema >/dev/null \
    && test -x /usr/bin/python3 \
    && ln -sf "$(command -v tmux)" /usr/local/bin/tmux \
    && ln -sf "$(command -v asciinema)" /usr/local/bin/asciinema \
    && test -x /usr/local/bin/tmux \
    && test -x /usr/local/bin/asciinema \
    && tmux -V \
    && asciinema --version \
    && TMPDIR=/tmp TMUX_TMPDIR=/tmp tmux new-session -d -s _agent_session_check \
    && TMPDIR=/tmp TMUX_TMPDIR=/tmp tmux has-session -t _agent_session_check \
    && TMPDIR=/tmp TMUX_TMPDIR=/tmp tmux kill-session -t _agent_session_check

# Verifier deps in a venv so they do not disturb apt python3 used by asciinema.
# Prefer /usr/bin/python3 explicitly when creating the venv.
RUN /usr/bin/python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
      pytest==8.4.1 \
      pytest-json-ctrf==0.3.5

COPY --from=rust-builder /usr/local/cargo /usr/local/cargo
COPY --from=rust-builder /usr/local/rustup /usr/local/rustup

# Preserve base PATH; put cargo + verifier ahead without dropping /usr/bin.
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH="/usr/local/cargo/bin:/opt/verifier/bin:/usr/local/bin:${PATH}" \
    CARGO_TARGET_DIR=/app/target \
    CARGO_NET_OFFLINE=true \
    DEBIAN_FRONTEND=noninteractive \
    TERM=xterm-256color \
    TMPDIR=/tmp \
    TMUX_TMPDIR=/tmp

RUN printf '%s\n' \
        'export PATH="/usr/local/cargo/bin:/opt/verifier/bin:/usr/local/bin:${PATH}"' \
        'export TMPDIR=/tmp' \
        'export TMUX_TMPDIR=/tmp' \
        'export TERM=xterm-256color' \
        > /etc/profile.d/agent-session-env.sh \
    && chmod 644 /etc/profile.d/agent-session-env.sh \
    && printf '%s\n' \
        'TMPDIR=/tmp' \
        'TMUX_TMPDIR=/tmp' \
        'TERM=xterm-256color' \
        >> /etc/environment

COPY --from=rust-builder /build/Cargo.toml /build/Cargo.lock /app/
COPY --from=rust-builder /build/w7x /app/w7x
COPY --from=rust-builder /build/p3n /app/p3n
COPY --from=rust-builder /build/k9m /app/k9m
COPY --from=rust-builder /build/v4q /app/v4q
COPY --from=rust-builder /build/probe /app/probe
COPY --from=rust-builder /build/native /app/native

COPY contracts /app/contracts
COPY docs /app/docs
COPY scripts /app/scripts
COPY requirements.txt /app/requirements.txt

RUN chmod +x /app/scripts/*.sh \
    && cargo fetch --locked \
    && cargo build -p probe --locked \
    && command -v cargo >/dev/null \
    && command -v rustc >/dev/null \
    && command -v tmux >/dev/null \
    && command -v asciinema >/dev/null \
    && test -x /usr/local/bin/tmux \
    && test -x /usr/local/bin/asciinema \
    && test -x /usr/bin/python3 \
    && asciinema --version \
    && TMPDIR=/tmp TMUX_TMPDIR=/tmp tmux new-session -d -s _agent_session_final \
    && TMPDIR=/tmp TMUX_TMPDIR=/tmp tmux has-session -t _agent_session_final \
    && TMPDIR=/tmp TMUX_TMPDIR=/tmp tmux kill-session -t _agent_session_final

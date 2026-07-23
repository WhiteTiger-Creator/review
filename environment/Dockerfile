FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS toolchain

FROM public.ecr.aws/docker/library/ubuntu:24.04@sha256:0d39fcc8335d6d74d5502f6df2d30119ff4790ebbb60b364818d5112d9e3e932

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV PATH="/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.12.3-0ubuntu2.1 \
    make=4.3-4.1build2 \
    ncurses-term=6.4+20240113-1ubuntu2.1 \
    bash=5.2.21-2ubuntu4 \
    ca-certificates=20260601~24.04.1 \
    tmux=3.4-1ubuntu0.1 \
    asciinema=2.4.0-1 \
    python3-venv=3.12.3-0ubuntu2.1 \
    patch=2.7.6-7build3 \
    build-essential=12.10ubuntu1 \
&& mkdir -p /var/tmp/tmux \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=bind,from=toolchain,source=/usr/local/cargo,target=/mnt/cargo,ro \
    --mount=type=bind,from=toolchain,source=/usr/local/rustup,target=/mnt/rustup,ro \
    cp -a /mnt/cargo /usr/local/cargo \
    && cp -a /mnt/rustup /usr/local/rustup

COPY runtime/tmux.conf /etc/tmux.conf

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY Cargo.toml Cargo.lock Makefile /app/environment/
COPY err.rs /app/environment/
COPY src /app/environment/src
COPY k2 /app/environment/k2
COPY m4 /app/environment/m4
COPY w3 /app/environment/w3
COPY r7 /app/environment/r7
COPY n5 /app/environment/n5
COPY p1 /app/environment/p1
COPY j0 /app/environment/j0
COPY support /app/environment/support
COPY configs /app/environment/configs
COPY data /app/environment/data
COPY docs /app/environment/docs
COPY scripts /app/environment/scripts
COPY entrypoint.sh /entrypoint.sh

WORKDIR /app/environment
RUN /usr/local/cargo/bin/cargo generate-lockfile \
    && make install \
    && mkdir -p /app/output /logs/verifier /logs/agent \
    && chmod +x /app/environment/scripts/run_matrix.sh /entrypoint.sh

WORKDIR /app
ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]

FROM debian:bookworm-slim@sha256:1d6cd964917a13b547d1ea392dff9a000c3f36070686ebc5c8755d53fb374435

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    cmake=3.25.1-1 \
    g++=4:12.2.0-3 \
    make=4.3-4.1 \
    ncurses-term=6.4-4 \
    ninja-build=1.11.1-2~deb12u1 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && mkdir -p /var/tmp/tmux \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

COPY runtime/tmux.conf /etc/tmux.conf

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

COPY include /app/environment/include
COPY b07 /app/environment/b07
COPY f12 /app/environment/f12
COPY n21 /app/environment/n21
COPY m14 /app/environment/m14
COPY c9 /app/environment/c9
COPY runner /app/environment/runner
COPY fixtures /app/environment/fixtures
COPY docs /app/environment/docs
COPY CMakeLists.txt /app/environment/CMakeLists.txt

RUN mkdir -p /app/output /app/build \
    && cmake -S /app/environment -B /app/build -G Ninja \
    && ninja -C /app/build forge_emit

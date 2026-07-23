FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV TERM=xterm-256color \
    TMUX_TMPDIR=/var/tmp/tmux

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bash binutils ca-certificates cmake file jq make musl-tools pkg-config python3 python3-venv tmux asciinema && mkdir -p /var/tmp/tmux && chmod 1777 /var/tmp/tmux && rm -rf /var/lib/apt/lists/* && python3 -m venv /opt/verifier-venv && /opt/verifier-venv/bin/python -m pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

ENV PATH="/opt/verifier-venv/bin:${PATH}"
WORKDIR /app
COPY runtime/tmux.conf /etc/tmux.conf
COPY CMakeLists.txt README.md /app/environment/
COPY cmake /app/environment/cmake
COPY config /app/environment/config
COPY docs /app/environment/docs
COPY include /app/environment/include
COPY engine /app/environment/engine
COPY scripts /app/environment/scripts
COPY src /app/environment/src

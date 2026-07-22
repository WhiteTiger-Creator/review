FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        cmake \
        libgrpc++-dev \
        libprotobuf-dev \
        ninja-build \
        pkg-config \
        protobuf-compiler \
        protobuf-compiler-grpc \
        python-is-python3 \
        python3 \
        python3-pip \
        tmux \
    && python3 -m pip install --break-system-packages --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5 \
    && rm -rf /var/lib/apt/lists/*

COPY task_file/ /app/
WORKDIR /app

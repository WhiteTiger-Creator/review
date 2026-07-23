FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pip \
        python-is-python3 \
        libmumps-seq-dev \
        liblapack-dev \
        libblas-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --break-system-packages \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

WORKDIR /app

COPY src /app/src
COPY include /app/include
COPY docs /app/docs
COPY data /app/data
COPY scripts /app/scripts
COPY Makefile /app/Makefile
COPY README.md /app/README.md

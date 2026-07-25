FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update && apt-get install -y --no-install-recommends \
      tmux asciinema python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --break-system-packages pytest==8.4.1

WORKDIR /app

COPY Makefile /app/Makefile
COPY README.md /app/README.md
COPY run_samples.sh /app/run_samples.sh
COPY src /app/src
COPY docs /app/docs
COPY data /app/data

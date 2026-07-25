FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends \
         asciinema ca-certificates make python3 python3-pytest tmux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY lyap.c /app/lyap.c
COPY build.sh /app/build.sh
COPY run.sh /app/run.sh
COPY docs /app/docs
COPY data /app/data
RUN chmod 0755 /app/build.sh /app/run.sh

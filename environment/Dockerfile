FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        tmux \
        asciinema \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    --require-hashes --no-deps -r /tmp/requirements.lock

WORKDIR /app

COPY starter/go.mod /app/go.mod
COPY spec/ /app/spec/
COPY data/ /app/data/
COPY starter/cmd/ /app/cmd/
COPY starter/internal/ /app/internal/

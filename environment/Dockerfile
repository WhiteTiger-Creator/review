FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV GOTOOLCHAIN=auto
ENV GOFLAGS=-buildvcs=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        bash \
        git \
        patch \
        ripgrep \
        less \
        nano \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --break-system-packages --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

WORKDIR /app
COPY repo/ /app/

RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"

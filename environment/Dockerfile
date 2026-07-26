# Canonical Edition 2 Go base from docs/PLATFORM_AUTO_EVAL.md
# (table row: golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac).
# public.ecr.aws/docker/library/ is the approved ECR mirror of docker.io/library.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive

# apt pins are point-in-time for Debian bookworm; refresh with
# `apt-cache madison <pkg>` if a security update removes an old version.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

# Offline verifier deps — baked at build time (allow_internet=false at runtime).
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        pyyaml==6.0.2

# Harbor/agent shells often reset PATH via login profiles; keep go + pytest
# discoverable for non-interactive and login shells.
RUN ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest \
    && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && printf '%s\n' \
        'export PATH=/usr/local/go/bin:/opt/verifier/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' \
        'export GOTOOLCHAIN=local' \
        'export GOFLAGS=-mod=mod' \
        > /etc/profile.d/tb3-path.sh \
    && test -x /usr/local/bin/go \
    && test -x /usr/local/bin/pytest \
    && go version

ENV PATH=/usr/local/go/bin:/opt/verifier/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV GOTOOLCHAIN=local
ENV GOFLAGS=-mod=mod
ENV GOCACHE=/tmp/adreq-gocache
ENV GOPATH=/tmp/adreq-gopath

WORKDIR /app

COPY . /app/environment

RUN mkdir -p /app/output /tmp/adreq-gocache /tmp/adreq-gopath \
    && cd /app/environment \
    && go build -o /tmp/xdrv ./cmd/xdrv \
    && test -x /tmp/xdrv

WORKDIR /app

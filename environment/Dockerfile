FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

# System packages required by the agent harness (tmux, asciinema) and the
# Python-based verifier.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        psmisc \
        python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Verifier dependencies are baked into the image: the verifier runs with
# networking disabled, so nothing may be installed at test time. The full
# transitive closure is pinned by hash in requirements.lock.
COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --no-cache-dir --break-system-packages \
    --require-hashes --no-deps -r /tmp/requirements.lock

# Pre-warm the Go module cache so `go build` works completely offline.
ENV GOMODCACHE=/opt/gomodcache \
    GOFLAGS=-mod=mod \
    GOPROXY=off \
    GOTOOLCHAIN=local

WORKDIR /app
COPY go.mod go.sum /app/
RUN GOPROXY=https://proxy.golang.org,direct go mod download all

# Task source: server stub and the shipped world definition.
COPY app/main.go /app/main.go
COPY app/world/ /app/world/
RUN mkdir -p /app/data

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        golang-go \
        make \
        patch \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

ENV GOPATH=/go \
    GOCACHE=/go/cache \
    GOFLAGS=-mod=mod \
    GO111MODULE=on \
    CGO_ENABLED=0

WORKDIR /app

COPY --chmod=0755 build.sh /app/build.sh
COPY Makefile go.mod /app/
COPY cmd/ /app/cmd/
COPY internal/ /app/internal/
COPY docs/ /app/docs/
COPY registry/ /app/registry/
COPY manifests/ /app/manifests/
COPY --chmod=0755 tools/ /app/tools/

RUN make all && ./tools/slate-selftest.sh

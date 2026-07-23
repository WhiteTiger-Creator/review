FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

ENV GOTOOLCHAIN=local
ENV GOFLAGS=-mod=mod
ENV GOCACHE=/tmp/gocache
ENV GOPATH=/tmp/go
ENV GOPROXY=off
ENV PATH="/usr/local/go/bin:/opt/verifier-venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        ca-certificates \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

COPY task_file/ /app/task_file/
RUN mkdir -p /app/task_file/output_data

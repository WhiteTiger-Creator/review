FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    GOTOOLCHAIN=local

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock

RUN python3 -m venv /opt/verifier_venv \
    && /opt/verifier_venv/bin/pip install --no-cache-dir \
        --require-hashes \
        -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock \
    && /opt/verifier_venv/bin/python -m pytest --version

WORKDIR /app/opaline

COPY go.mod README.md ./
COPY *.go ./
COPY docs/ ./docs/
COPY examples/ ./examples/

RUN GOPROXY=off GOSUMDB=off GOWORK=off go test ./... \
    && GOPROXY=off GOSUMDB=off GOWORK=off go vet ./...

CMD ["sleep", "infinity"]

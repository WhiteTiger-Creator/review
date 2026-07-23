# Canonical Terminal-Bench Go final runtime base (docs/PLATFORM_AUTO_EVAL.md):
# golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        PyYAML==6.0.2
ENV PATH=/opt/verifier/bin:/usr/local/go/bin:${PATH}
ENV GOTOOLCHAIN=local GOFLAGS=-mod=mod GOPROXY=off

RUN mkdir -p /app/environment /app/output/stage /logs/verifier /tmp/gocache /tmp/gopath

COPY go.mod /app/environment/go.mod
COPY m3 /app/environment/m3
COPY p9 /app/environment/p9
COPY r5 /app/environment/r5
COPY cmd /app/environment/cmd
COPY tools /app/environment/tools
COPY docs /app/environment/docs
COPY data /app/environment/data

RUN chmod +x /app/environment/tools/build.sh \
    && cd /app/environment \
    && bash tools/build.sh \
    && rm -rf /app/output \
    && mkdir -p /app/output/stage

WORKDIR /app

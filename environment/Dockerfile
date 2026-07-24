FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update     && apt-get install -y --no-install-recommends         tmux         asciinema         ca-certificates         python3         python3-venv     && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv     && /opt/verifier-venv/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

WORKDIR /app/environment

COPY go.mod ./go.mod
COPY cmd ./cmd
COPY internal ./internal
COPY systemd ./systemd
COPY etc ./etc
COPY generated ./generated
COPY docs ./docs
COPY fixtures ./fixtures
COPY runtime ./runtime

RUN mkdir -p /app/bin /app/output /app/environment/var/lib     && go build -trimpath -ldflags="-s -w" -o /app/bin/collectorctl ./cmd/collectorctl     && sha256sum /app/bin/collectorctl > /app/environment/var/lib/collectorctl.sha256

WORKDIR /app

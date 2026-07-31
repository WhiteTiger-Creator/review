FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

LABEL org.opencontainers.image.title="Racklight fleet maintenance control host"
LABEL org.opencontainers.image.description="Offline host environment for coordinated rack change windows"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        python3=3.11.2-1+b1 \
        python3-venv=3.11.2-1+b1 \
        tmux=3.3a-3 \
        util-linux=2.38.1-5+deb12u3 \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
    && ln -s /usr/local/go/bin/go /usr/local/bin/go \
    && ln -s /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && useradd --create-home --uid 10001 --user-group --shell /bin/bash drainwave

RUN mkdir -p /app && chown 10001:10001 /app

WORKDIR /app

COPY --chown=10001:10001 CHANGE_CONTROL_RUNBOOK.md /app/CHANGE_CONTROL_RUNBOOK.md
COPY --chown=10001:10001 go.mod /app/go.mod
COPY --chown=10001:10001 main.go /app/main.go
COPY --chown=10001:10001 internal /app/internal
COPY --chown=10001:10001 --chmod=0755 build.sh /app/build.sh

# Keep the container's default user as root so Harbor can create and mount its
# runtime directories. The verifier still rebuilds and executes drainwave as UID 10001.

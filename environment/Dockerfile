FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS signd-builder

WORKDIR /build
COPY signd-src/ ./
RUN go build -ldflags="-s -w" -o /build/authgw-signd .

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        curl \
        ca-certificates \
        python3 \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:${PATH}"
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

WORKDIR /app

# Fetch Go module dependencies in their own layer so source edits below
# don't invalidate the download cache. This also means the module cache
# already lives in the image, so the agent and verifier never need
# network access to build or run authgw.
COPY app/go.mod app/go.sum ./
RUN go mod download

COPY app/ ./
COPY --from=signd-builder /build/authgw-signd /app/bin/authgw-signd

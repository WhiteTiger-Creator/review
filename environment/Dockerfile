FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS go-builder
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        ca-certificates \
        gcc \
        libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=go-builder /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}"

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

WORKDIR /app
COPY app /app

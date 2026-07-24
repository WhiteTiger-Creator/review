FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
      tmux=3.3a-3 \
      asciinema=2.2.0-1 \
      libgomp1=12.2.0-14+deb12u1 \
      ca-certificates=20230311+deb12u1 \
      r-base-core=4.2.2.20221110-2 \
      r-cran-jsonlite=1.8.4+dfsg-1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/test-venv \
    && /opt/test-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

RUN mkdir -p /app/outputs \
    && touch /app/analysis.R \
    && chown 65534:65534 /app/analysis.R /app/outputs

COPY data/ /app/data/
COPY config/ /app/config/
COPY docs/ /app/docs/

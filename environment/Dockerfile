FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
      tmux asciinema libgomp1 ca-certificates \
      r-base-core r-cran-jsonlite && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/test-venv \
    && /opt/test-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

RUN mkdir -p /app/outputs

COPY data/ /app/data/
COPY config/ /app/config/
COPY docs/ /app/docs/

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema bash ca-certificates \
        coreutils findutils gawk git \
        grep gzip jq sed tar tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip install --require-hashes \
    --no-deps --no-cache-dir \
    -r /tmp/requirements.lock

COPY task_file/ /app/
RUN chmod +x /app/bin/freeze-bazel-registry

ENV PYTHONPATH=/app

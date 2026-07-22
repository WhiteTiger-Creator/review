FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        g++ \
        cmake \
        make \
        ca-certificates \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/environment

COPY requirements.lock /app/environment/requirements.lock
RUN python3 -m venv /opt/test-venv \
    && /opt/test-venv/bin/pip install --no-cache-dir --require-hashes -r /app/environment/requirements.lock

COPY CMakeLists.txt README.md build.sh /app/environment/
COPY data/ /app/environment/data/
COPY include/ /app/environment/include/
COPY src/ /app/environment/src/
COPY docs/ /app/environment/docs/

RUN chmod +x build.sh

WORKDIR /app/environment

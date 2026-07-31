# Canonical, digest-pinned base image (Python family - provides python3 for the
# pytest verifier).
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

# tmux + asciinema are REQUIRED by the agent runtime. golang-go builds the
# supervisor.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        golang-go \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Hash-locked verifier deps (requirements.lock). Baked at build time so test.sh
# never touches the network (task.toml: allow_internet = false).
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock

WORKDIR /app
COPY go.mod PROTOCOL.md /app/
COPY cmd/ /app/cmd/
COPY samples/ /app/samples/
RUN mkdir -p /app/out \
    && go build -o /app/reclaim ./cmd/reclaim

CMD ["/bin/bash"]

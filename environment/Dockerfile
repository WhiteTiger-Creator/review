FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        less \
        nano \
        procps \
        python3 \
        python-is-python3 \
        python3-pip \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

# The task is solved and verified offline. Keep Go on the bundled toolchain,
# reject module lookups, and make accidental runtime pip resolution fail closed.
ENV GOTOOLCHAIN=local \
    GOPROXY=off \
    GOSUMDB=off \
    GOFLAGS=-mod=readonly \
    PIP_NO_INDEX=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY task_file /app/task_file
RUN rm -rf /app/task_file/out && mkdir -p /app/task_file/out

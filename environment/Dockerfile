FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv tmux asciinema \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /go/bin \
    && ln -sf /usr/local/go/bin/go /go/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /go/bin/gofmt \
    && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

WORKDIR /app
COPY task_file/ /app/

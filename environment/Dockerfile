FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/output

COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --no-cache-dir --break-system-packages \
    -r /tmp/requirements.lock

# The Go toolchain remains in the runtime image because both the agent and verifier
# compile the planner after source edits.
COPY go.mod /app/environment/go.mod
COPY cmd/ /app/environment/cmd/
COPY docs/ /app/environment/docs/
COPY k9m/ /app/environment/k9m/
COPY n2p/ /app/environment/n2p/
COPY pkg/ /app/environment/pkg/
COPY r4x/ /app/environment/r4x/
COPY scenarios/ /app/environment/scenarios/
COPY vendor_tree/ /app/environment/vendor_tree/

WORKDIR /app
ENV PATH="/usr/local/go/bin:${PATH}"

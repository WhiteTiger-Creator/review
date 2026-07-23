FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

LABEL org.opencontainers.image.title="NIST beacon audit workstation" \
      org.opencontainers.image.description="Go cryptographic verification toolkit for retained randomness-beacon evidence" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.licenses="Apache-2.0"

# Verifier dependencies are baked in so test.sh remains offline and never installs packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/local/bin/python

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --break-system-packages --no-cache-dir --require-hashes \
        --no-deps -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

WORKDIR /app

COPY go.mod /app/go.mod
COPY cmd/ /app/cmd/
COPY internal/ /app/internal/
RUN go build -trimpath -ldflags='-s -w' -o /usr/local/bin/beacon-audit ./cmd/beacon-audit

COPY docs/ /app/docs/
COPY schemas/ /app/schemas/
COPY cases/ /app/cases/
COPY policies/ /app/policies/
COPY trust/ /app/trust/
COPY examples/ /app/examples/

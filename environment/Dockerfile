# Canonical Terminal-Bench Go 1.24 bookworm (docs/PLATFORM_AUTO_EVAL.md, Go row).
# Image: golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac
# Mirror: public.ecr.aws/docker/library/golang — same digest as the sanctioned canonical entry.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN rm -f /etc/apt/sources.list.d/debian.sources \
    && printf 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260101T000000Z bookworm main\n' > /etc/apt/sources.list \
    && printf 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20260101T000000Z bookworm-security main\n' >> /etc/apt/sources.list

RUN ln -sf /usr/local/go/bin/go /usr/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/bin/gofmt

RUN apt-get update && apt-get install -y --no-install-recommends make=4.3-4.1 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.txt
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt
RUN rm -f /tmp/requirements.txt

COPY go.mod go.sum Makefile ingest.go ./environment/
COPY cmd ./environment/cmd
COPY internal ./environment/internal
COPY slice ./environment/slice
COPY slot ./environment/slot
COPY memo ./environment/memo
COPY range ./environment/range
COPY pipeline ./environment/pipeline
COPY bundle ./environment/bundle
COPY data ./environment/data
COPY docs ./environment/docs
COPY tools/dy ./environment/tools/dy
COPY tools/check-k7.sh ./environment/tools/check-k7.sh

RUN cd /app/environment \
    && go mod download \
    && mkdir -p bin /opt/k7probe \
    && go build -o /opt/k7probe/dy ./cmd/k7probe \
    && go build -o bin/w7 ./cmd/w7 \
    && chmod +x /app/environment/tools/dy /app/environment/tools/check-k7.sh /opt/k7probe/dy

ENV PATH=/app/environment/bin:/opt/verifier/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

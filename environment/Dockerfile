# Build context must be environment/ only (Harbor CONTEXT_DIR). Never build from task root.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS builder
WORKDIR /build
COPY . /build/environment
WORKDIR /build/environment
RUN go build -o /build/out/wave_sched ./cmd/wave_sched && go build -o /build/out/epochctl ./cmd/epochctl

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential=12.9 golang-go=2:1.19~1 make=4.3-4.1 tmux=3.3a-3 asciinema=2.2.0-1 ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5
ENV PATH=/opt/verifier/bin:${PATH}

RUN mkdir -p /app/environment /app/output /app/environment/bin

COPY . /app/environment
COPY --from=builder /usr/local/go /usr/local/go
COPY --from=builder /build/out/wave_sched /app/environment/bin/wave_sched
COPY --from=builder /build/out/epochctl /app/environment/bin/epochctl
ENV PATH=/usr/local/go/bin:/opt/verifier/bin:${PATH}

RUN python3 /app/environment/scripts/gen_fixtures.py \
    && echo -n 0 > /app/environment/pack/seed/.roll_scratch \
    && echo -n 0 > /app/environment/pack/seed/.storm_gen \
    && printf '%s\n' '{"token":0,"bound_gen":1,"storm_ok":true,"rev":1}' > /app/environment/pack/seed/.epoch_bus.json \
    && cp /app/environment/pack/seed/token_seed.bin /app/environment/pack/seed/.anchor_staging \
    && chmod +x /app/environment/scripts/*.sh /app/environment/phase/*.sh

CMD ["python3", "-c", "print('Environment ready')"]

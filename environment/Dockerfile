# Build stage: compile the audited decoder into a stripped binary. Its source is
# used only here and never enters the final image, so the audited decoder is
# staged as a black box the agent must characterize by probing, not by reading.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS build
WORKDIR /build
COPY audited/decoder.rs /build/decoder.rs
RUN rustc -O -C strip=symbols /build/decoder.rs -o /build/decoder

FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages pytest==8.3.3 pytest-json-ctrf==0.3.5

WORKDIR /app

# Immutable evidence: the audited decoder as a runnable black-box binary only.
COPY --from=build /build/decoder /app/environment/evidence/decoder
RUN chmod +x /app/environment/evidence/decoder

COPY docs/ /app/environment/docs/
COPY analysis/ /app/environment/analysis/

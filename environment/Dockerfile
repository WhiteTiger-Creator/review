# TB3 environment image for histopathology-stain-robustness-auditor-0763.
#
# Canonical runtime base (Terminal-Bench ECR library mirror):
# public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d
#
# Multi-stage layout: hs-builder compiles hs_driver; the runtime stage installs a
# pinned g++/cmake toolchain so agents can recompile after C++ fixes under
# allow_internet=false (verifier reruns the full HS cycle).
#
# Offline execution: apt packages are version-pinned; verifier Python deps install
# from requirements.lock via pip --require-hashes.

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d AS hs-builder

WORKDIR /app/environment

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake=3.25.1-1 \
    g++=4:12.2.0-3 \
    make=4.3-4.1 \
    nlohmann-json3-dev=3.11.2-2 \
    libssl-dev=3.0.20-1~deb12u2 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY CMakeLists.txt ./
COPY corpus/ corpus/
COPY docs/ docs/
COPY exec/ exec/
COPY hs_driver/ hs_driver/
COPY j2n/ j2n/
COPY k8m/ k8m/
COPY logging/ logging/
COPY o9_chk/ o9_chk/
COPY r3k/ r3k/
COPY s4d/ s4d/
COPY schemas/ schemas/
COPY tooling/ tooling/
COPY w7p/ w7p/

RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --target hs_driver -j"$(nproc)"

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake=3.25.1-1 \
    g++=4:12.2.0-3 \
    make=4.3-4.1 \
    nlohmann-json3-dev=3.11.2-2 \
    libssl-dev=3.0.20-1~deb12u2 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/output /app/output/stage

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt

ENV PATH=/opt/verifier/bin:${PATH}

COPY --from=hs-builder /app/environment/build /app/environment/build

WORKDIR /app/environment
COPY CMakeLists.txt ./
COPY corpus/ corpus/
COPY docs/ docs/
COPY exec/ exec/
COPY hs_driver/ hs_driver/
COPY j2n/ j2n/
COPY k8m/ k8m/
COPY logging/ logging/
COPY o9_chk/ o9_chk/
COPY r3k/ r3k/
COPY s4d/ s4d/
COPY schemas/ schemas/
COPY tooling/ tooling/
COPY w7p/ w7p/

RUN chmod +x exec/*.sh o9_chk/*.sh tooling/*.sh

ENV PATH=/app/environment/build:${PATH}

WORKDIR /app
CMD ["bash", "-c", "echo Environment ready"]

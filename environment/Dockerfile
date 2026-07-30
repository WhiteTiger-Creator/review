FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    g++=4:12.2.0-3 \
    cmake=3.25.1-1 \
    make=4.3-4.1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    openssl=3.0.20-1~deb12u2 \
    nlohmann-json3-dev=3.11.2-2 \
    libssl-dev=3.0.20-1~deb12u2 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    && rm -rf /var/lib/apt/lists/*

# Verifier-only: pytest harness. Agent engine sources live under /app/environment (g++/cmake), not Python.
RUN python3 -m venv /opt/verifier \
                && /opt/verifier/bin/pip install --no-cache-dir \
                    pytest==8.4.1 \
                    pytest-json-ctrf==0.3.5 \
                    pytest-randomly==3.16.0
ENV PATH=/opt/verifier/bin:${PATH}

COPY CMakeLists.txt deps.cmake /app/
COPY annex/ /app/annex/
COPY corpora/ /app/corpora/
COPY desk/ /app/desk/
COPY docs/ /app/docs/
COPY fixtures/ /app/fixtures/
COPY stage_p/ /app/stage_p/
COPY stage_q/ /app/stage_q/
COPY stage_r/ /app/stage_r/
COPY stage_t/ /app/stage_t/
COPY stage_j/ /app/stage_j/
COPY stage_v/ /app/stage_v/
COPY pvsim /app/pvsim
COPY README.md /app/README.md

RUN chmod +x /app/pvsim \
    && mkdir -p /app/environment \
    && ln -sfn /app/stage_p /app/environment/stage_p \
    && ln -sfn /app/stage_q /app/environment/stage_q \
    && ln -sfn /app/stage_r /app/environment/stage_r \
    && ln -sfn /app/stage_t /app/environment/stage_t \
    && ln -sfn /app/stage_j /app/environment/stage_j \
    && ln -sfn /app/stage_v /app/environment/stage_v \
    && ln -sfn /app/desk /app/environment/desk \
    && cmake -S /app -B /app/build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /app/build -j$(nproc) \
    && mkdir -p /app/runtime/dossier /app/runtime/transcript /app/runtime/journal

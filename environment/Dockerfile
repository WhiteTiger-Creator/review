FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS collector-build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY internal ./internal
COPY pkg ./pkg
COPY cmd ./cmd
RUN cargo build --release --locked --bin apkfold --bin apk-board \
    && mkdir -p /locked \
    && install -m 0755 target/release/apkfold /locked/apkfold \
    && install -m 0755 target/release/apk-board /locked/apk-board

FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV PATH="/usr/local/cargo/bin:${PATH}"

# Session tools first (tmux + asciinema), then build/verifier runtime deps.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1 \
        pkg-config=1.8.1-1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
    && rm -rf /var/lib/apt/lists/* \
    && command -v tmux \
    && command -v asciinema \
    && tmux -V \
    && asciinema --version

RUN ln -sf /usr/bin/python3 /usr/bin/python

COPY wheels /opt/wheels
ENV PIP_NO_INDEX=1
ENV PIP_FIND_LINKS=/opt/wheels
RUN pip3 install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

COPY --from=collector-build /usr/local/cargo/registry /usr/local/cargo/registry
COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY internal ./internal
COPY pkg ./pkg
COPY cmd ./cmd
COPY config ./config
COPY data ./data
COPY docs ./docs
COPY harness ./harness
COPY schemas ./schemas
COPY ops ./ops
COPY README.md ./README.md
COPY scripts ./scripts
COPY ci ./ci

RUN chmod +x /app/scripts/*.sh /app/ci/*.sh /app/ops/helpers/*.sh \
    && bash /app/scripts/build.sh \
    && command -v tmux \
    && command -v asciinema

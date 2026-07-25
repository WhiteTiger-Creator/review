FROM rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV PATH="/usr/local/cargo/bin:${PATH}"
ENV CARGO_NET_OFFLINE=true
ENV CARGO_TERM_COLOR=never

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --break-system-packages pytest==8.3.4

WORKDIR /app

COPY Cargo.toml Cargo.lock README.md check_build.sh ./
COPY src ./src
COPY docs ./docs
COPY data ./data

RUN chmod +x check_build.sh

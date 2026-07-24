FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3-venv \
        tmux \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir --disable-pip-version-check \
        --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock \
    && find /opt/venv -type d -exec chmod go-w {} + \
    && find /opt/venv -type f -exec chmod go-w {} +

ENV PATH="/opt/venv/bin:/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    CARGO_HOME="/usr/local/cargo" \
    RUSTUP_HOME="/usr/local/rustup"
RUN ln -sf /usr/local/cargo/bin/cargo /usr/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/bin/rustc

WORKDIR /app
# Agent runs as uid 65534; world-writable tree without recursive permission flags.
COPY --chmod=0777 app/ /app/
RUN chmod 0777 /app

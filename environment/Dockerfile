FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36
RUN apt-get update && apt-get install -y --no-install-recommends asciinema passwd python3 python3-pip python3-venv tmux util-linux \
    && ln -s /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && ln -s /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash candidate
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier-venv && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
WORKDIR /app
COPY --chown=candidate:candidate analysis.rs /app/analysis.rs
COPY docs /app/docs
COPY data /app/data
RUN chown candidate:candidate /app

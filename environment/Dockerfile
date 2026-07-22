# Canonical Terminal-Bench Node base, digest-pinned for reproducibility.
FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

ENV DEBIAN_FRONTEND=noninteractive
COPY requirements.lock /tmp/requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        git \
        ripgrep \
        patch \
        make \
        unzip \
        curl \
        ca-certificates \
        python3 \
        python3-venv \
    && python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
    && rm -rf /var/lib/apt/lists/*

# node:slim ships python3 for the base OS but pytest and its hash-locked plugins
# live in a dedicated virtualenv; expose that interpreter as a wrapper script
# (not a symlink) so pytest resolves from the locked environment.
RUN printf '#!/bin/sh\nexec /opt/verifier-venv/bin/python3 "$@"\n' > /usr/local/bin/python3 \
    && chmod 0755 /usr/local/bin/python3
ENV VERIFIER_PYTHON=/opt/verifier-venv/bin/python3

WORKDIR /app
COPY repo/ /app/

# Install the siftfit command that runs the built service.
RUN install -m 0755 /app/siftfit /usr/local/bin/siftfit

# Prime the build, then drop the artifact so rebuilds start clean.
RUN make dist/main.mjs && rm -rf /app/dist

# /app is a git repo so git apply / git diff work in place.
RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"

# Canonical C base. The compiler toolchain must remain in the runtime image
# because building the shipped CMake project is the task itself.
FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        cmake \
        python3 \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps \
        -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

COPY app/ /app/
COPY osv/ /var/lib/osv/
RUN mkdir -p /app/out

WORKDIR /app

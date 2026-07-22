FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

# The triage script recompiles the C++ source after the agent's repair.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        python3-venv=3.11.2-1+b1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install \
        --no-cache-dir \
        --disable-pip-version-check \
        --require-hashes \
        --no-deps \
        -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

ENV PATH="/opt/venv/bin:${PATH}"
RUN printf '%s\n' 'export PATH="/opt/venv/bin:$PATH"' > /etc/profile.d/sleep-apnea-path.sh

WORKDIR /app
COPY app/ /app/
RUN chmod +x /app/scripts/run-triage.sh

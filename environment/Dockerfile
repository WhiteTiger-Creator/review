# Canonical sanctioned Java base image (digest-pinned)
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

WORKDIR /app

LABEL task="cosign-quorum-auditor"
ENV TASK_BUILD_REV="cqa-ledger-1"

# Unprivileged account for candidate execution during verification; the test
# harness demotes every invocation of /app/audit to this user so the candidate
# cannot read the reference implementation under /tests.
RUN useradd --system --no-create-home --shell /usr/sbin/nologin sandbox \
    && mkdir -p /app/output && chmod 1777 /app/output

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        ca-certificates \
        python3 \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Verifier test dependencies, fully hash-pinned and baked into the image (no
# runtime network installs).
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
        --require-hashes --no-deps -r /tmp/requirements.lock
ENV PATH="/opt/venv/bin:${PATH}"

COPY app/ /app/

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

# Install NodeSource GPG key, Node.js 20, and build-essential (for compiling native tfjs bindings)
RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema \
    curl \
    ca-certificates \
    gnupg \
    python3-venv \
    tmux \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        nodejs \
        build-essential \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifests and locks
COPY verifier-requirements.lock /tmp/verifier-requirements.lock
COPY app/package.json app/package-lock.json /app/

# Install verifier dependencies in an isolated venv and Node.js dependencies
RUN python3 -m venv --system-site-packages /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --require-hashes --no-deps --no-cache-dir -r /tmp/verifier-requirements.lock \
    && npm ci

COPY app/tsconfig.json /app/

# Copy application source and assets
COPY app/src/ /app/src/
COPY app/data/ /app/data/
COPY app/docs/ /app/docs/
COPY app/fixtures/ /app/fixtures/

# Pre-compile the application
RUN npx tsc


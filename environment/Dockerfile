FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-venv \
        make \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir pytest==8.3.4 \
    && rm -rf /var/lib/apt/lists/*

# The agent session runs as this restricted, non-root user (task.toml sets
# [agent].user = "agent"). The image build and verifier still run as root
# (no USER directive), so the verifier can write /logs/verifier. Pytest is
# invoked from the root-owned venv at /opt/venv, which the agent uid cannot
# overwrite, so neither the interpreter nor the pytest module can be shadowed.
RUN groupadd --system agent \
    && useradd --system --gid agent --create-home --home-dir /home/agent agent

WORKDIR /app

COPY main.go /app/main.go
COPY select.go /app/select.go
COPY go.mod /app/go.mod
COPY docs/ /app/docs/
COPY data/ /app/data/
COPY Makefile /app/Makefile

# /app is the agent's workspace: it edits select.go and builds ./resolve there.
# Make it agent-owned so the non-root session can write, while /opt/venv and the
# system interpreters stay root-owned and unmodifiable.
RUN chown -R agent:agent /app

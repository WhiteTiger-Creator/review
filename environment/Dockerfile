FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        jq \
        file \
        tmux \
        asciinema \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pinned pytest plus the CTRF reporter plugin (for --ctrf output). Debian
# bookworm's apt pytest predates the API the plugin needs.
RUN pip3 install --no-cache-dir --break-system-packages \
        pytest==8.3.4 \
        pytest-json-ctrf==0.5.2

# The agent's solving script is expected in Rust: rustc/cargo are on PATH from
# the base image. No crates are vendored (no external dependency, no network
# fetch risk) -- std alone is sufficient for this task's flat JSON schemas, so
# there is nothing to configure offline the way Go's GOPROXY=off does.

# Two users: "agent" runs the task (unprivileged); "oracle" owns the sealed
# daemon so the agent can execute it but cannot read the hidden retention
# rules, copy the binary, or ptrace it.
RUN useradd -m -u 1000 agent && useradd -m -u 1001 oracle

# The daemon ships as a prebuilt, sealed executable. Its source is deliberately
# not part of this build context, so the hidden retention rules never exist in
# readable form anywhere in the agent-facing environment. The source of record
# lives in solution/engine.go (outside this context) and is compiled offline
# with CGO_ENABLED=0 -trimpath -ldflags="-s -w" for a static, stripped binary.
COPY daemon/decide /opt/retention/decide
RUN printf '0' > /opt/retention/.count

# Public material handed to the agent: the audit request set and worked
# examples.
RUN mkdir -p /app/challenge /app/out
COPY challenge/requests.json /app/challenge/requests.json
COPY challenge/examples.json /app/challenge/examples.json

# Seal the oracle side: directory traversable but not listable; query counter
# private to oracle; daemon set-uid + execute-only.
RUN chown oracle:oracle /opt/retention /opt/retention/decide /opt/retention/.count \
    && chmod 0711 /opt/retention \
    && chmod 0600 /opt/retention/.count \
    && chmod 4711 /opt/retention/decide

# Hand the working area to the agent. No USER directive here, deliberately: the
# container default must stay privileged so the verifier can create and write
# /logs/verifier/reward.txt on a harness-provided root-owned /logs. The agent's
# own unprivileged execution comes from [agent].user in task.toml instead.
RUN chown agent:agent /app /app/out /app/challenge

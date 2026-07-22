# Current submission policy lists this exact digest-pinned ECR Go image as the
# canonical Go final base.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update &&     apt-get install -y --no-install-recommends       asciinema       ca-certificates       python3       python3-pip       python3-venv       tmux       util-linux &&     ln -sf /usr/local/go/bin/go /usr/local/bin/go &&     rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages --require-hashes -r /tmp/requirements.txt

RUN groupadd --gid 10001 candidate && useradd --uid 10001 --gid 10001 --create-home candidate

WORKDIR /app

COPY go.mod /app/go.mod
COPY challenge/ /app/challenge/
COPY docs/ /app/docs/
COPY samples/ /app/samples/
COPY cmd/ /app/cmd/
COPY internal/ /app/internal/
COPY tools/ /app/tools/

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends python3 python3-venv tmux asciinema ca-certificates && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/verifier-venv
COPY requirements.lock /tmp/requirements.lock
RUN /opt/verifier-venv/bin/pip --disable-pip-version-check install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock
WORKDIR /app
COPY task_file/ /app/task_file/
RUN mkdir -p /app/cmd/lockout-guard /app/bin /app/out

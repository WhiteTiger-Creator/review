FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       asciinema \
       python3 \
       python3-pytest \
       tmux \
    && rm -rf /var/lib/apt/lists/*

COPY app/ /app/

RUN chmod +x /app/bin/build-tidefront /app/bin/tidefront \
    && mkdir -p /logs/agent /output

CMD ["sleep", "infinity"]

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac
RUN apt-get update && apt-get install -y --no-install-recommends tmux asciinema python3 python3-pytest && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app /app/app
CMD ["bash"]
